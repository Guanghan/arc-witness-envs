"""Data models for human teaching sessions.

Captures per-step reasoning annotations and episode-level outcomes
from human game demonstrations.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TeachingStep(BaseModel):
    """One step in a human teaching session."""

    step_index: int
    frame_hash: str                     # SHA256 of 64×64 frame
    action: int                         # ACTION1-5
    reasoning: str = ""                 # Human's thought process (free text)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    timestamp: float = 0.0
    tags: List[str] = Field(default_factory=list)


class EpisodeOutcome(BaseModel):
    """Outcome annotation for a completed episode."""

    game_id: str
    level_index: int
    completed: bool
    total_steps: int
    baseline_steps: Optional[int] = None
    efficiency: Optional[float] = None
    key_insights: List[str] = Field(default_factory=list)
    rules_discovered: List[str] = Field(default_factory=list)
    difficulty_rating: int = Field(default=3, ge=1, le=5)


class TeachingEpisode(BaseModel):
    """Complete teaching episode: steps + outcome."""

    episode_id: str                     # UUID
    game_id: str
    level_index: int
    seed: int = 0
    steps: List[TeachingStep] = Field(default_factory=list)
    outcome: Optional[EpisodeOutcome] = None
    created_at: str = ""                # ISO datetime
    teacher_id: str = "default"
