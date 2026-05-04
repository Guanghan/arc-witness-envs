"""Eval runner — orchestrates an agent across one or many games.

Agent-agnostic: any object satisfying `bench.protocols.AgentProtocol` can
be evaluated. The runner owns game loading and authoritative scoring; the
agent just plays.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

from .catalog import list_games, load_game, load_game_info
from .protocols import AgentProtocol
from .scoring import first_n_hit_counts, score_one_game
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
        game = load_game(game_id, seed=seed)
    except Exception as e:
        log.exception("[%s] failed to load game", game_id)
        return (
            _zero_score(game_id, info.scoreable_levels),
            {},
            time.perf_counter() - t0,
            f"load_game: {type(e).__name__}: {e}",
        )

    try:
        result: AgentRunResult = agent.run_on_game(
            game,
            game_id,
            seed=seed,
            verbose=verbose,
            max_levels=max_levels,
        )
    except Exception as e:
        log.exception("[%s] agent runtime error", game_id)
        return (
            _zero_score(game_id, info.scoreable_levels),
            {},
            time.perf_counter() - t0,
            f"{type(e).__name__}: {e}",
        )

    # Single source of truth: overwrite baseline_actions from WitnessGameInfo.
    n_baselines = len(info.baseline_actions)
    for lo in result.levels:
        if 0 <= lo.level_index < n_baselines:
            lo.baseline_actions = info.baseline_actions[lo.level_index]

    score = score_one_game(info, result)
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
    """
    if game_ids is None:
        game_ids = list_games()

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
        total_elapsed_s=total_elapsed,
        overall_score=(sum(s.score for s in scores) / len(scores)) if scores else 0.0,
        first_n_completed=first_n_hit_counts(scores),
    )

    return BenchmarkReport(
        agent=agent_info or AgentInfo(name="unknown"),
        seed=seed,
        games=entries,
        summary=summary,
        run_metadata=run_metadata or {},
    )
