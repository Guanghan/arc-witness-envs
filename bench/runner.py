"""Eval runner — orchestrates an agent across one or many games.

Agent-agnostic: any object satisfying `bench.protocols.AgentProtocol` can
be evaluated. The runner owns game loading and authoritative scoring; the
agent just plays.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .catalog import list_games, load_game, load_game_info
from .protocols import AgentProtocol
from .scoring import (
    aggregate_runs,
    compute_tag_scores,
    first_n_hit_counts,
    score_one_game,
)
from .types import (
    AgentInfo,
    AgentRunResult,
    BenchmarkReport,
    BenchmarkSummary,
    GameReportEntry,
    LevelOutcome,
    WitnessScore,
)


log = logging.getLogger(__name__)


# Optional oversight toolbox (snapshot/fork/oracle). Import-guarded: when the
# `oversight/` package is absent this falls back to identity, so bench scoring
# is byte-identical with or without it (removability tripwire: GATE-R1).
# OversightEnv is a transparent passthrough; it composes UNDER the reset
# counter as _ResetCountingGame(OversightEnv(bare)) so snapshots only ever see
# the bare game and the reset counter / scorecard stay structurally excluded.
try:
    from oversight import OversightEnv as _OversightEnv
except ImportError:  # package removed -> no-op wrapper
    def _OversightEnv(game):
        return game


class _ResetCountingGame:
    """Transparent proxy that counts RESET actions performed via the env.

    Wraps the game object handed to the agent. Forwards every attribute and
    `perform_action` call to the underlying game; only side effect is
    incrementing `reset_count` when the action is a RESET. The benchmark
    then becomes the single source of truth for per-game reset counts —
    independent of whether the agent itself tracks them.
    """

    def __init__(self, game: Any) -> None:
        self._game = game
        self.reset_count: int = 0

    def perform_action(self, action_input: Any) -> Any:
        # arcengine.GameAction.RESET == 0; we identify by enum name to avoid
        # a hard import here (and to be robust to id renumbering).
        action_id = getattr(action_input, "id", None)
        action_name = getattr(action_id, "name", None)
        if action_name == "RESET":
            self.reset_count += 1
        return self._game.perform_action(action_input)

    def __getattr__(self, name: str) -> Any:
        # Forward anything else to the wrapped game.
        return getattr(self._game, name)


def _zero_score(game_id: str, scoreable_levels: int) -> WitnessScore:
    return WitnessScore(
        game_id=game_id,
        score=0.0,
        levels_completed=0,
        levels_total=scoreable_levels,
        actions=0,
    )


def run_single_game(
    agent: AgentProtocol,
    game_id: str,
    seed: int = 0,
    max_levels: Optional[int] = None,
    verbose: bool = False,
    score_cap: Optional[int] = None,
) -> Tuple[WitnessScore, Dict[str, Any], float, Optional[str]]:
    """Run an agent on a single game and score the result.

    Returns:
        (score, agent_extras, elapsed_s, error_or_none)

    The runner overrides each `LevelOutcome.baseline_actions` from the
    canonical `WitnessGameInfo.baseline_actions[i]` before scoring, so the
    agent never has to know the benchmark's baselines.
    """
    info = load_game_info(game_id)
    t0 = time.perf_counter()

    try:
        raw_game = load_game(game_id, seed=seed)
    except Exception as e:
        log.exception("[%s] failed to load game", game_id)
        return (
            _zero_score(game_id, min(info.scoreable_levels, score_cap) if score_cap and score_cap > 0 else info.scoreable_levels),
            {},
            time.perf_counter() - t0,
            f"load_game: {type(e).__name__}: {e}",
        )

    # Wrap the game so we can authoritatively count RESETs at the bench
    # boundary, regardless of whether the agent tracks them itself. The
    # inner _OversightEnv is a transparent passthrough (identity when the
    # oversight package is absent), so this is byte-identical to wrapping
    # raw_game directly.
    counting_game = _ResetCountingGame(_OversightEnv(raw_game))

    try:
        result: AgentRunResult = agent.run_on_game(
            counting_game,
            game_id,
            seed=seed,
            verbose=verbose,
            max_levels=max_levels,
        )
    except Exception as e:
        log.exception("[%s] agent runtime error", game_id)
        return (
            _zero_score(game_id, min(info.scoreable_levels, score_cap) if score_cap and score_cap > 0 else info.scoreable_levels),
            {},
            time.perf_counter() - t0,
            f"{type(e).__name__}: {e}",
        )

    # Single source of truth: overwrite baseline_actions from WitnessGameInfo
    # and resets from the bench-side counter.
    n_baselines = len(info.baseline_actions)
    for lo in result.levels:
        if 0 <= lo.level_index < n_baselines:
            lo.baseline_actions = info.baseline_actions[lo.level_index]
    result.resets = counting_game.reset_count

    score = score_one_game(info, result, score_cap=score_cap)
    return score, dict(result.extra), time.perf_counter() - t0, None


def run_batch(
    agent: AgentProtocol,
    game_ids: Optional[List[str]] = None,
    seed: int = 0,
    max_levels: Optional[int] = None,
    verbose: bool = False,
    agent_info: Optional[AgentInfo] = None,
    run_metadata: Optional[Dict[str, Any]] = None,
    on_game_done: Optional[Any] = None,
    score_cap: Optional[int] = None,
) -> BenchmarkReport:
    """Evaluate an agent across multiple games and produce a BenchmarkReport.

    Args:
        agent: Anything satisfying AgentProtocol.
        game_ids: Subset of games to run. None = all 13 witness games.
        seed: Random seed for game generation.
        max_levels: Optional per-game level cap (passed through to the agent).
        verbose: Forward to the agent.
        agent_info: Identity card for the agent (model, version, etc.).
            Defaults to AgentInfo(name="unknown").
        run_metadata: Free-form dict (CLI args, config snapshot, git sha).
        on_game_done: Optional callable(game_id, score, elapsed_s, error)
            called after each game finishes. Useful for live progress prints.
        score_cap: Optional per-game level cap applied during scoring. When
            set, only the first ``score_cap`` levels of each game are scored;
            level-index weights for levels beyond the cap are excluded from
            both numerator and denominator. Pair with a matching ``max_levels``
            so the agent doesn't waste action budget on unscored levels.
            Default ``None`` preserves SDK-equivalent full-game scoring.
    """
    if game_ids is None:
        game_ids = list_games()

    # Pre-load all WitnessGameInfo so we can compute tag scores at the end.
    infos = {gid: load_game_info(gid) for gid in game_ids}

    entries: List[GameReportEntry] = []
    scores: List[WitnessScore] = []
    total_t0 = time.perf_counter()

    for i, gid in enumerate(game_ids, 1):
        log.info("[%d/%d] Running %s", i, len(game_ids), gid)
        score, extras, elapsed, err = run_single_game(
            agent,
            gid,
            seed=seed,
            max_levels=max_levels,
            verbose=verbose,
            score_cap=score_cap,
        )

        entries.append(
            GameReportEntry(
                game_id=gid,
                score=score,
                elapsed_s=elapsed,
                error=err,
                legacy={"agent_extras": extras} if extras else None,
            )
        )
        scores.append(score)

        if on_game_done is not None:
            try:
                on_game_done(gid, score, elapsed, err)
            except Exception:
                log.warning("on_game_done callback raised:\n%s", traceback.format_exc())

    total_elapsed = time.perf_counter() - total_t0

    summary = BenchmarkSummary(
        total_games=len(entries),
        successful_games=sum(1 for e in entries if e.error is None),
        total_levels_completed=sum(s.levels_completed for s in scores),
        total_levels=sum(s.levels_total for s in scores),
        total_actions=sum(s.actions for s in scores),
        total_resets=sum((s.resets or 0) for s in scores),
        total_elapsed_s=total_elapsed,
        overall_score=(sum(s.score for s in scores) / len(scores)) if scores else 0.0,
        first_n_completed=first_n_hit_counts(scores),
        tag_scores=compute_tag_scores(entries, infos, score_cap=score_cap),
    )

    return BenchmarkReport(
        agent=agent_info or AgentInfo(name="unknown"),
        seed=seed,
        games=entries,
        summary=summary,
        run_metadata=run_metadata or {},
    )


def run_batch_multi_seed(
    agent: AgentProtocol,
    game_ids: Optional[List[str]] = None,
    seeds: Sequence[int] = (0,),
    max_levels: Optional[int] = None,
    verbose: bool = False,
    agent_info: Optional[AgentInfo] = None,
    run_metadata: Optional[Dict[str, Any]] = None,
    on_game_done: Optional[Any] = None,
    score_cap: Optional[int] = None,
) -> BenchmarkReport:
    """Multi-seed evaluation: run the agent on each game with each seed,
    then aggregate per-game results via MAX (per official ARC-AGI-3 SDK
    behavior, `arc_agi.scorecard.EnvironmentScoreList.score = max(...)`).

    Args:
        agent: any AgentProtocol-conforming object.
        game_ids: subset of games (None = all 13 witness games).
        seeds: seeds to run. Single-seed shortcut: pass a one-element seq.
        max_levels: per-game level cap.
        verbose, agent_info, run_metadata: forwarded.
        on_game_done: called per (seed, game) finish — useful for live logs.

    Output BenchmarkReport.games[i].score is the MAX-aggregate over runs;
    per-run details are preserved in `games[i].legacy["per_run_scores"]`,
    `["per_run_elapsed"]`, `["per_run_errors"]`, with `["best_run_idx"]` and
    `["per_run_seeds"]` for traceability. `run_metadata` gains `"seeds"`
    and `"n_runs"`.

    Single-seed shortcut: `len(seeds) == 1` delegates to `run_batch` so the
    output shape is identical to the single-run path.
    """
    if not seeds:
        raise ValueError("seeds must be non-empty")
    if game_ids is None:
        game_ids = list_games()

    seeds = list(seeds)
    n_runs = len(seeds)

    # Single-seed shortcut: identical behavior to run_batch.
    if n_runs == 1:
        return run_batch(
            agent=agent,
            game_ids=game_ids,
            seed=seeds[0],
            max_levels=max_levels,
            verbose=verbose,
            agent_info=agent_info,
            run_metadata={
                **(run_metadata or {}),
                "seeds": seeds,
                "n_runs": 1,
            },
            on_game_done=on_game_done,
            score_cap=score_cap,
        )

    # Multi-seed: collect results in (game, run) buckets.
    per_game_scores: Dict[str, List[WitnessScore]] = {gid: [] for gid in game_ids}
    per_game_extras: Dict[str, List[Dict[str, Any]]] = {gid: [] for gid in game_ids}
    per_game_elapsed: Dict[str, List[float]] = {gid: [] for gid in game_ids}
    per_game_errors: Dict[str, List[Optional[str]]] = {gid: [] for gid in game_ids}

    total_t0 = time.perf_counter()

    for seed_idx, seed in enumerate(seeds, 1):
        log.info("=== Run %d/%d (seed=%d) ===", seed_idx, n_runs, seed)
        for game_idx, gid in enumerate(game_ids, 1):
            log.info("  [%d/%d] seed=%d %s", game_idx, len(game_ids), seed, gid)
            score, extras, elapsed, err = run_single_game(
                agent,
                gid,
                seed=seed,
                max_levels=max_levels,
                verbose=verbose,
                score_cap=score_cap,
            )
            per_game_scores[gid].append(score)
            per_game_extras[gid].append(extras)
            per_game_elapsed[gid].append(elapsed)
            per_game_errors[gid].append(err)

            if on_game_done is not None:
                try:
                    on_game_done(gid, score, elapsed, err)
                except Exception:
                    log.warning(
                        "on_game_done callback raised:\n%s", traceback.format_exc()
                    )

    total_elapsed = time.perf_counter() - total_t0

    # Aggregate per game (MAX over runs).
    infos = {gid: load_game_info(gid) for gid in game_ids}
    entries: List[GameReportEntry] = []
    aggregated_scores: List[WitnessScore] = []

    for gid in game_ids:
        scores = per_game_scores[gid]
        agg = aggregate_runs(scores)

        # Best-run index = argmax over per-run score (ties → earliest)
        best_run_idx = max(range(len(scores)), key=lambda i: scores[i].score)
        best_run_extras = per_game_extras[gid][best_run_idx]
        best_run_elapsed = per_game_elapsed[gid][best_run_idx]

        # Error reporting: only flag the game as errored if EVERY run errored.
        # Otherwise the agent succeeded at least once → success.
        errors_seen = per_game_errors[gid]
        all_errored = all(e is not None for e in errors_seen)
        err_msg: Optional[str]
        if all_errored:
            err_msg = "; ".join(set(e for e in errors_seen if e))
        else:
            err_msg = None

        entries.append(
            GameReportEntry(
                game_id=gid,
                score=agg,
                elapsed_s=best_run_elapsed,
                error=err_msg,
                legacy={
                    "agent_extras": best_run_extras,
                    "per_run_seeds": list(seeds),
                    "per_run_scores": [
                        s.model_dump(exclude_none=True) for s in scores
                    ],
                    "per_run_elapsed": list(per_game_elapsed[gid]),
                    "per_run_errors": list(per_game_errors[gid]),
                    "best_run_idx": best_run_idx,
                },
            )
        )
        aggregated_scores.append(agg)

    summary = BenchmarkSummary(
        total_games=len(entries),
        successful_games=sum(1 for e in entries if e.error is None),
        total_levels_completed=sum(s.levels_completed for s in aggregated_scores),
        total_levels=sum(s.levels_total for s in aggregated_scores),
        total_actions=sum(s.actions for s in aggregated_scores),
        total_resets=sum((s.resets or 0) for s in aggregated_scores),
        total_elapsed_s=total_elapsed,
        overall_score=(
            sum(s.score for s in aggregated_scores) / len(aggregated_scores)
            if aggregated_scores
            else 0.0
        ),
        first_n_completed=first_n_hit_counts(aggregated_scores),
        tag_scores=compute_tag_scores(entries, infos, score_cap=score_cap),
    )

    return BenchmarkReport(
        agent=agent_info or AgentInfo(name="unknown"),
        seed=seeds[0],  # primary seed; full list in run_metadata
        games=entries,
        summary=summary,
        run_metadata={
            **(run_metadata or {}),
            "seeds": list(seeds),
            "n_runs": n_runs,
        },
    )
