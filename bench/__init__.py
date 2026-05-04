"""Witness benchmark — evaluation infrastructure for arc-witness-envs.

Mirrors the official ARC-AGI-3 SDK scoring methodology
(see arc_agi/scorecard.py) so any agent implementing AgentProtocol can be
evaluated identically against the witness benchmark (tw01–tw13).

Public exports:

    Types:           WitnessGameInfo, WitnessScore, LevelOutcome, AgentRunResult,
                     AgentInfo, GameReportEntry, BenchmarkSummary, BenchmarkReport,
                     WitnessGameState
    Scoring:         WitnessScoreCalculator, score_one_game, first_n_hit_counts,
                     aggregate_runs
    Catalog:         GAME_CLASSES, list_games, load_game, load_game_info
    Protocols:       AgentProtocol
    Runner:          run_single_game, run_batch
"""

from .types import (
    AgentInfo,
    AgentRunResult,
    BenchmarkReport,
    BenchmarkSummary,
    GameReportEntry,
    LevelOutcome,
    TagScore,
    WitnessGameInfo,
    WitnessGameState,
    WitnessScore,
)
from .scoring import (
    WitnessScoreCalculator,
    aggregate_runs,
    compute_tag_scores,
    first_n_hit_counts,
    score_one_game,
)
from .catalog import GAME_CLASSES, list_games, load_game, load_game_info
from .protocols import AgentProtocol
from .runner import run_batch, run_batch_multi_seed, run_single_game

__all__ = [
    "AgentInfo",
    "AgentProtocol",
    "AgentRunResult",
    "BenchmarkReport",
    "BenchmarkSummary",
    "GAME_CLASSES",
    "GameReportEntry",
    "LevelOutcome",
    "TagScore",
    "WitnessGameInfo",
    "WitnessGameState",
    "WitnessScore",
    "WitnessScoreCalculator",
    "aggregate_runs",
    "compute_tag_scores",
    "first_n_hit_counts",
    "list_games",
    "load_game",
    "load_game_info",
    "run_batch",
    "run_batch_multi_seed",
    "run_single_game",
    "score_one_game",
]

__version__ = "2.0.0"
