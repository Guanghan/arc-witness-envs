"""Pydantic types for the Witness benchmark.

Mirrors the conceptual shape of `arc_agi.models.EnvironmentInfo` and
`arc_agi.scorecard.{EnvironmentScore, EnvironmentScoreList}` with
Witness-specific naming.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


class WitnessGameState(str, Enum):
    """Mirrors arcengine.GameState — duplicated here so bench has no
    hard dependency on arc_agi/arcengine."""

    NOT_PLAYED = "NOT_PLAYED"
    NOT_FINISHED = "NOT_FINISHED"
    WIN = "WIN"
    GAME_OVER = "GAME_OVER"


class WitnessGameInfo(BaseModel):
    """Static metadata about a Witness benchmark game.

    Loaded from `environment_files/<game_id>/metadata.json` plus
    `levels/<game_id>_levels.json`. Mirrors `EnvironmentInfo` from arc_agi.
    """

    game_id: str
    title: Optional[str] = None
    class_name: Optional[str] = None
    tags: Optional[List[str]] = None
    private_tags: Optional[List[str]] = None
    level_tags: Optional[List[List[str]]] = None
    baseline_actions: List[int] = Field(default_factory=list)
    real_total_levels: int = 0
    date_downloaded: Optional[datetime] = None

    @computed_field(return_type=int)  # type: ignore[prop-decorator]
    @property
    def scoreable_levels(self) -> int:
        """Number of levels that have a baseline (== `len(baseline_actions)`).

        This is the authoritative denominator for scoring — independent of
        what the agent reports as its highest reached level.
        """
        return len(self.baseline_actions)


class LevelOutcome(BaseModel):
    """Per-level result that an agent reports back to the scorer.

    Maps 1:1 to args of `WitnessScoreCalculator.add_level()`. The scorer
    overwrites `baseline_actions` from the canonical `WitnessGameInfo`
    before calling `add_level`, so agents don't need to populate it.
    """

    level_index: int  # 0-based as the agent emits them; runner maps to 1-based for SDK-style weighting
    completed: bool
    actions_taken: int
    baseline_actions: int = 0  # filled by runner from WitnessGameInfo
    # Optional context — preserved in the report, not used in scoring:
    stage_actions: Dict[str, int] = Field(default_factory=dict)
    llm_calls: int = 0


class WitnessScore(BaseModel):
    """Per-game score. Mirrors `arc_agi.scorecard.EnvironmentScore`."""

    game_id: str
    score: float  # 0..115, 1-based-level-weighted average
    levels_completed: int
    levels_total: int  # = WitnessGameInfo.scoreable_levels
    actions: int
    resets: Optional[int] = None
    state: Optional[WitnessGameState] = None
    completed: Optional[bool] = None
    level_scores: List[float] = Field(default_factory=list)
    level_actions: List[int] = Field(default_factory=list)
    level_baseline_actions: List[int] = Field(default_factory=list)
    message: Optional[str] = None

    def model_dump_json(self, *, exclude_none: bool = True, **kwargs: Any) -> str:
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)


class AgentRunResult(BaseModel):
    """What an agent must return after running a single game.

    Agent-side wrappers convert their internal per-game metrics into this
    shape: a `levels` list of `LevelOutcome`s, total action / reset counts,
    terminal state, and free-form `extra` for telemetry the scorer ignores.
    """

    game_id: str
    seed: int = 0
    levels: List[LevelOutcome] = Field(default_factory=list)
    total_actions: int = 0
    resets: int = 0
    state: Optional[WitnessGameState] = None
    # Free-form agent telemetry — preserved in the report but not scored:
    extra: Dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    """Identity card for the agent under test, written into the report."""

    name: str
    version: Optional[str] = None
    config_hash: Optional[str] = None
    description: Optional[str] = None
    extras: Dict[str, Any] = Field(default_factory=dict)


class GameReportEntry(BaseModel):
    """One game's slot in a BenchmarkReport."""

    game_id: str
    score: WitnessScore
    elapsed_s: float = 0.0
    error: Optional[str] = None
    # Pass-through for agent-internal data we want to preserve in the report
    # (e.g., the legacy GameMetrics dump):
    legacy: Optional[Dict[str, Any]] = None


class TagScore(BaseModel):
    """Aggregate score over the subset of games carrying a given tag.

    Aggregation method is **mean of per-game scores** (no per-level
    re-weighting — each game already carries its own intra-game weighted
    score). This makes interpretation simple: "average witness-score on
    games tagged X".
    """

    tag: str
    mean_score: float
    total_games: int
    total_levels_completed: int
    total_levels: int  # sum of scoreable_levels across tagged games
    total_actions: int
    game_ids: List[str] = Field(default_factory=list)


class BenchmarkSummary(BaseModel):
    """Aggregate summary across all games in a run."""

    total_games: int = 0
    successful_games: int = 0
    total_levels_completed: int = 0
    total_levels: int = 0  # sum of scoreable_levels across games
    total_actions: int = 0
    total_resets: int = 0  # sum of per-game resets
    total_elapsed_s: float = 0.0
    overall_score: float = 0.0  # mean of per-game scores
    first_n_completed: Dict[int, int] = Field(default_factory=dict)
    # e.g., {1: 10, 3: 7, 5: 5, 10: 2} = "for K in cutoffs, how many games had levels_completed >= K"
    tag_scores: Dict[str, TagScore] = Field(default_factory=dict)
    # Per-tag aggregate views; keys are tag names from WitnessGameInfo.tags.


class BenchmarkReport(BaseModel):
    """Top-level result object — what gets serialized to JSON."""

    schema_version: str = "2.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: AgentInfo
    seed: int = 0
    games: List[GameReportEntry] = Field(default_factory=list)
    summary: BenchmarkSummary = Field(default_factory=BenchmarkSummary)
    run_metadata: Dict[str, Any] = Field(default_factory=dict)
