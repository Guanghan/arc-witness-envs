"""Scoring algorithm — port of `arc_agi.scorecard.EnvironmentScoreCalculator`.

The scoring formulas here are bit-for-bit equivalent to the reference at
`arc_agi/scorecard.py:117-228` (verified via `tests/test_scoring.py`).

Per-level:
    score = ((baseline_actions / actions_taken) ** 2) * 100, capped at 115
    score = 0 if not completed or actions_taken == 0

Per-game (`to_score`):
    weight = level_index (1-based)
    score  = sum(level_scores * weights) / sum(weights)
    score  = min(score, max_weights / total_weights * 100)
        where max_weights = sum of weights for levels with score > 0

Multi-run (`aggregate_runs`):
    score             = max over runs
    levels_completed  = max over runs
    resets            = sum over runs
"""

from __future__ import annotations

from typing import Iterable, List, Mapping, Optional, Sequence

from .types import AgentRunResult, WitnessGameInfo, WitnessGameState, WitnessScore


SCORE_CAP: float = 115.0


class WitnessScoreCalculator:
    """Stateful per-game score calculator.

    Mirrors `arc_agi.scorecard.EnvironmentScoreCalculator` exactly. Add one
    `add_level(level_index, completed, actions_taken, baseline_actions)`
    call per game-defined level (NOT per agent attempt — driven by the
    benchmark, not the agent), then call `to_score()` once at the end.
    """

    def __init__(
        self,
        game_id: str,
        resets: Optional[int] = None,
        state: Optional[WitnessGameState] = None,
    ) -> None:
        self.game_id: str = game_id
        self.resets: Optional[int] = resets
        self.state: Optional[WitnessGameState] = state
        self.completed: Optional[bool] = None
        self.levels_completed: int = 0
        self.actions: int = 0
        self.level_indices: List[int] = []
        self.level_scores: List[float] = []
        self.level_actions: List[int] = []
        self.level_baseline_actions: List[int] = []

    def add_level(
        self,
        level_index: int,
        completed: bool,
        actions_taken: int,
        baseline_actions: int,
    ) -> None:
        self.actions += actions_taken
        if completed:
            self.levels_completed += 1
            if actions_taken > 0:
                score = ((baseline_actions / actions_taken) ** 2) * 100
                score = min(score, SCORE_CAP)
            else:
                score = 0.0
        else:
            score = 0.0
        self.level_indices.append(level_index)
        self.level_scores.append(score)
        self.level_actions.append(actions_taken)
        self.level_baseline_actions.append(baseline_actions)

    def to_score(self) -> WitnessScore:
        if not self.level_scores:
            score: float = 0.0
        else:
            total_score = 0.0
            total_weights = 0
            max_weights = 0
            for i, s in enumerate(self.level_scores):
                w = self.level_indices[i]
                total_score += s * w
                total_weights += w
                if s > 0:
                    max_weights += w
            if total_weights == 0:
                # Pathological: all level_indices are 0 (caller used 0-based?)
                # Fall back to unweighted mean.
                score = sum(self.level_scores) / len(self.level_scores)
            else:
                score = total_score / total_weights
                max_score = max_weights / total_weights * 100
                score = min(score, max_score)

        return WitnessScore(
            game_id=self.game_id,
            score=score,
            levels_completed=self.levels_completed,
            levels_total=len(self.level_scores),
            actions=self.actions,
            resets=self.resets,
            state=self.state,
            completed=self.completed,
            level_scores=list(self.level_scores),
            level_actions=list(self.level_actions),
            level_baseline_actions=list(self.level_baseline_actions),
        )


# ── Helpers ──────────────────────────────────────────────────────────────


def score_one_game(
    game_info: WitnessGameInfo,
    run: AgentRunResult,
) -> WitnessScore:
    """Drive a `WitnessScoreCalculator` from an `AgentRunResult`.

    Iterates `range(game_info.scoreable_levels)` — NOT `len(run.levels)` —
    so missing levels score 0 (matching SDK behavior). The agent's
    `LevelOutcome.level_index` is treated as 0-based; the scorer adds +1
    to get SDK-style 1-based weights.
    """
    by_idx: Mapping[int, "AgentRunResult"] = {lo.level_index: lo for lo in run.levels}  # type: ignore[assignment]

    calc = WitnessScoreCalculator(
        game_id=game_info.game_id,
        resets=run.resets,
        state=run.state,
    )

    for level_idx in range(game_info.scoreable_levels):
        baseline = game_info.baseline_actions[level_idx]
        outcome = by_idx.get(level_idx)
        if outcome is None:
            calc.add_level(
                level_index=level_idx + 1,  # 1-based for weighting
                completed=False,
                actions_taken=0,
                baseline_actions=baseline,
            )
        else:
            calc.add_level(
                level_index=level_idx + 1,
                completed=bool(outcome.completed),
                actions_taken=int(outcome.actions_taken),
                baseline_actions=baseline,
            )

    calc.completed = run.state == WitnessGameState.WIN
    return calc.to_score()


def first_n_hit_counts(
    scores: Sequence[WitnessScore],
    cutoffs: Iterable[int] = (1, 3, 5, 10, 20, 50),
) -> dict:
    """For each cutoff K in `cutoffs`, count games with `levels_completed >= K`.

    Returns a dict like `{1: 10, 3: 7, 5: 5, 10: 2}` — useful for
    "first-N hit rate" reporting.
    """
    return {k: sum(1 for s in scores if s.levels_completed >= k) for k in cutoffs}


def aggregate_runs(scores_by_run: Sequence[WitnessScore]) -> WitnessScore:
    """Multi-run max-aggregate (mirrors `arc_agi.scorecard.EnvironmentScoreList`).

        score             = max over runs
        levels_completed  = max over runs
        resets            = sum over runs
        completed         = any over runs

    Per-level detail is intentionally elided (the SDK does the same):
    "best run wins" is a per-run abstraction, not per-level.
    """
    if not scores_by_run:
        raise ValueError("scores_by_run must be non-empty")
    first = scores_by_run[0]
    return WitnessScore(
        game_id=first.game_id,
        score=max(s.score for s in scores_by_run),
        levels_completed=max(s.levels_completed for s in scores_by_run),
        levels_total=first.levels_total,
        actions=sum(s.actions for s in scores_by_run),
        resets=sum((s.resets or 0) for s in scores_by_run),
        completed=any(bool(s.completed) for s in scores_by_run),
    )
