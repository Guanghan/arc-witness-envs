"""TeachingCollector — in-memory buffer + JSONL persistence for teaching data.

Usage:
    collector = TeachingCollector(data_dir="teaching_data")
    collector.start_episode("tw01", level_index=0)
    collector.record_step(TeachingStep(step_index=0, frame_hash="abc", action=4, reasoning="go right"))
    collector.finish_episode(EpisodeOutcome(game_id="tw01", level_index=0, completed=True, total_steps=5))
    # Episode is automatically persisted to teaching_data/tw01/episodes.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import EpisodeOutcome, TeachingEpisode, TeachingStep

logger = logging.getLogger(__name__)


class TeachingCollector:
    """Collects and persists human teaching demonstrations."""

    def __init__(self, data_dir: str = "teaching_data"):
        self._data_dir = data_dir
        self._active_episode: Optional[TeachingEpisode] = None
        self._completed: List[TeachingEpisode] = []
        os.makedirs(data_dir, exist_ok=True)

    # ── Episode Lifecycle ──────────────────────────────────

    def start_episode(
        self, game_id: str, level_index: int, seed: int = 0
    ) -> str:
        """Start a new teaching episode. Returns episode_id."""
        # Auto-finish previous episode if still active
        if self._active_episode is not None:
            self.finish_episode(None)

        episode_id = uuid.uuid4().hex[:12]
        self._active_episode = TeachingEpisode(
            episode_id=episode_id,
            game_id=game_id,
            level_index=level_index,
            seed=seed,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(
            f"Teaching episode started: {game_id} L{level_index} "
            f"(id={episode_id})"
        )
        return episode_id

    def record_step(self, step: TeachingStep) -> bool:
        """Record one step with reasoning annotation.

        Returns True if recorded, False if no active episode.
        """
        if self._active_episode is None:
            logger.warning("No active episode; ignoring step")
            return False
        # Auto-set timestamp if not provided
        if step.timestamp == 0.0:
            step.timestamp = time.time()
        self._active_episode.steps.append(step)
        return True

    def finish_episode(
        self, outcome: Optional[EpisodeOutcome]
    ) -> Optional[TeachingEpisode]:
        """Finish the active episode and persist to disk.

        Returns the completed episode, or None if no active episode.
        """
        if self._active_episode is None:
            return None

        episode = self._active_episode
        episode.outcome = outcome
        self._active_episode = None

        # Persist
        self._persist_episode(episode)
        self._completed.append(episode)

        logger.info(
            f"Teaching episode finished: {episode.game_id} "
            f"L{episode.level_index} — {len(episode.steps)} steps, "
            f"completed={outcome.completed if outcome else 'unknown'}"
        )
        return episode

    @property
    def active_episode(self) -> Optional[TeachingEpisode]:
        return self._active_episode

    @property
    def step_count(self) -> int:
        """Number of steps in the active episode."""
        if self._active_episode is None:
            return 0
        return len(self._active_episode.steps)

    # ── Persistence ──────────────────────────────────────

    def _persist_episode(self, episode: TeachingEpisode):
        """Append episode to JSONL file."""
        game_dir = os.path.join(self._data_dir, episode.game_id)
        os.makedirs(game_dir, exist_ok=True)
        filepath = os.path.join(game_dir, "episodes.jsonl")
        with open(filepath, "a") as f:
            f.write(episode.model_dump_json() + "\n")

    # ── Loading ──────────────────────────────────────

    def load_episodes(self, game_id: str) -> List[TeachingEpisode]:
        """Load all episodes for a game from disk."""
        filepath = os.path.join(self._data_dir, game_id, "episodes.jsonl")
        if not os.path.exists(filepath):
            return []
        episodes = []
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    episodes.append(
                        TeachingEpisode.model_validate_json(line)
                    )
        return episodes

    def load_all_episodes(self) -> Dict[str, List[TeachingEpisode]]:
        """Load episodes for all games."""
        result: Dict[str, List[TeachingEpisode]] = {}
        if not os.path.isdir(self._data_dir):
            return result
        for game_id in sorted(os.listdir(self._data_dir)):
            game_dir = os.path.join(self._data_dir, game_id)
            if os.path.isdir(game_dir):
                episodes = self.load_episodes(game_id)
                if episodes:
                    result[game_id] = episodes
        return result

    def get_episode(self, episode_id: str) -> Optional[TeachingEpisode]:
        """Find a specific episode by ID across all games."""
        # Check in-memory first
        if (
            self._active_episode
            and self._active_episode.episode_id == episode_id
        ):
            return self._active_episode
        for ep in self._completed:
            if ep.episode_id == episode_id:
                return ep
        # Search on disk
        all_eps = self.load_all_episodes()
        for episodes in all_eps.values():
            for ep in episodes:
                if ep.episode_id == episode_id:
                    return ep
        return None

    def list_episodes_summary(self) -> List[dict]:
        """List summary of all episodes (for API response)."""
        all_eps = self.load_all_episodes()
        summaries = []
        for game_id, episodes in all_eps.items():
            for ep in episodes:
                summaries.append({
                    "episode_id": ep.episode_id,
                    "game_id": ep.game_id,
                    "level_index": ep.level_index,
                    "steps": len(ep.steps),
                    "completed": (
                        ep.outcome.completed if ep.outcome else None
                    ),
                    "created_at": ep.created_at,
                })
        return summaries
