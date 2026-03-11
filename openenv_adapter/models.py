"""
Pydantic models for the arc-witness OpenEnv adapter.

Maps ARC-AGI-3 GameAction (1-5) to OpenEnv Action/Observation types.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class WitnessGameAction(str, Enum):
    """Discrete actions matching ARC-AGI-3 ACTION1-ACTION5."""
    UP = "UP"          # ACTION1
    DOWN = "DOWN"      # ACTION2
    LEFT = "LEFT"      # ACTION3
    RIGHT = "RIGHT"    # ACTION4
    CONFIRM = "CONFIRM"  # ACTION5


class WitnessAction(Action):
    """Action sent to the witness environment."""
    action: WitnessGameAction = Field(
        ..., description="Direction to move or CONFIRM to submit solution."
    )


class WitnessObservation(Observation):
    """Observation returned from the witness environment."""
    frame: List[List[int]] = Field(
        ..., description="64x64 grid of color indices (0-15)."
    )
    level_index: int = Field(
        0, description="Current level index within the game."
    )
    levels_completed: int = Field(
        0, description="Total levels completed so far."
    )
    total_levels: int = Field(
        0, description="Total number of levels in this game."
    )
    available_actions: List[int] = Field(
        default_factory=list,
        description="Available action IDs (1-5).",
    )
    message: str = Field(
        "", description="Status message."
    )
    reward: float = Field(0.0, description="Step reward.")
    done: bool = Field(False, description="Whether the episode (level) ended.")
