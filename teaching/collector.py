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


def player_slug(teacher_id: str) -> str:
    """Normalize a player name ONCE at the boundary (data-contract rule 2):
    identity is case-insensitive and path-safe, so "Bob" / "bob " are one
    player and one directory. Display name keeps the raw form."""
    import re
    s = re.sub(r"[^a-z0-9_-]+", "-", (teacher_id or "default").strip().lower())
    return s.strip("-") or "default"


class TeachingCollector:
    """Collects and persists human teaching demonstrations.

    Concurrency (2026-07-23, shared-server deployment): active episodes are
    keyed by episode_id with one live slot PER PLAYER — concurrent players
    never interleave. Endpoints route steps/outcomes by episode_id; the
    single-active-episode legacy API (no episode_id) still works when exactly
    one episode is live, so solo/local flows are unchanged.
    """

    def __init__(self, data_dir: str = "teaching_data"):
        self._data_dir = data_dir
        import threading
        self._lock = threading.Lock()
        self._active: Dict[str, TeachingEpisode] = {}   # episode_id -> episode
        self._completed: List[TeachingEpisode] = []
        os.makedirs(data_dir, exist_ok=True)

    # ── Episode Lifecycle ──────────────────────────────────

    def start_episode(
        self, game_id: str, level_index: int, seed: int = 0,
        teacher_id: str = "default",
    ) -> str:
        """Start a new teaching episode. Returns episode_id.
        One live episode per player: starting a new one auto-finishes the
        player's previous episode (recorded-but-unannotated, never lost)."""
        with self._lock:
            slug = player_slug(teacher_id)
            stale = [eid for eid, ep in self._active.items()
                     if player_slug(ep.teacher_id) == slug]
        for eid in stale:
            self.finish_episode(None, episode_id=eid)

        episode_id = uuid.uuid4().hex[:12]
        ep = TeachingEpisode(
            episode_id=episode_id,
            game_id=game_id,
            level_index=level_index,
            seed=seed,
            created_at=datetime.now(timezone.utc).isoformat(),
            teacher_id=(teacher_id or "default").strip() or "default",
        )
        with self._lock:
            self._active[episode_id] = ep
        logger.info(
            f"Teaching episode started: {game_id} L{level_index} "
            f"(id={episode_id}, player={player_slug(teacher_id)})"
        )
        return episode_id

    def _resolve(self, episode_id: Optional[str]) -> Optional[TeachingEpisode]:
        """episode_id -> episode; None resolves ONLY when unambiguous
        (exactly one live episode — the legacy solo API)."""
        with self._lock:
            if episode_id:
                return self._active.get(episode_id)
            if len(self._active) == 1:
                return next(iter(self._active.values()))
        return None

    def record_step(self, step: TeachingStep,
                    episode_id: Optional[str] = None) -> bool:
        """Record one step. Returns True if recorded."""
        ep = self._resolve(episode_id)
        if ep is None:
            logger.warning("No (unambiguous) active episode; ignoring step")
            return False
        if step.timestamp == 0.0:
            step.timestamp = time.time()
        with self._lock:
            ep.steps.append(step)
        return True

    def finish_episode(
        self, outcome: Optional[EpisodeOutcome],
        episode_id: Optional[str] = None,
    ) -> Optional[TeachingEpisode]:
        """Finish an active episode and persist to disk."""
        ep = self._resolve(episode_id)
        if ep is None:
            return None
        with self._lock:
            self._active.pop(ep.episode_id, None)
        ep.outcome = outcome
        self._persist_episode(ep)
        self._completed.append(ep)
        logger.info(
            f"Teaching episode finished: {ep.game_id} "
            f"L{ep.level_index} — {len(ep.steps)} steps, "
            f"completed={outcome.completed if outcome else 'unknown'} "
            f"(player={player_slug(ep.teacher_id)})"
        )
        return ep

    @property
    def active_episode(self) -> Optional[TeachingEpisode]:
        """Legacy solo accessor: the episode iff exactly one is live."""
        return self._resolve(None)

    def step_count(self, episode_id: Optional[str] = None) -> int:
        """Steps in the given (or sole) active episode."""
        ep = self._resolve(episode_id)
        return len(ep.steps) if ep is not None else 0

    # ── Persistence ──────────────────────────────────────

    def _persist_episode(self, episode: TeachingEpisode):
        """Append to the player-keyed stream (data-contract rule 1):
        teaching_data/players/<player-slug>/<game>/episodes.jsonl — identity
        in the PATH, so per-player ops are directory ops and concurrent
        players never share an append file. Legacy shared files
        (teaching_data/<game>/episodes.jsonl) remain read-only grandfathered
        in every consumer."""
        game_dir = os.path.join(self._data_dir, "players",
                                player_slug(episode.teacher_id),
                                episode.game_id)
        os.makedirs(game_dir, exist_ok=True)
        filepath = os.path.join(game_dir, "episodes.jsonl")
        with self._lock:
            with open(filepath, "a") as f:
                f.write(episode.model_dump_json() + "\n")

    # ── Loading ──────────────────────────────────────

    def load_episodes(self, game_id: str) -> List[TeachingEpisode]:
        """Load all episodes for a game from disk — every player's stream
        (players/<slug>/<game>/) plus the legacy shared file."""
        paths = [os.path.join(self._data_dir, game_id, "episodes.jsonl")]
        players_root = os.path.join(self._data_dir, "players")
        if os.path.isdir(players_root):
            for slug in sorted(os.listdir(players_root)):
                paths.append(os.path.join(players_root, slug, game_id,
                                          "episodes.jsonl"))
        episodes = []
        for filepath in paths:
            if not os.path.exists(filepath):
                continue
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
        names = set()
        for d in [self._data_dir] + (
                [os.path.join(self._data_dir, "players", s)
                 for s in os.listdir(os.path.join(self._data_dir, "players"))]
                if os.path.isdir(os.path.join(self._data_dir, "players")) else []):
            if os.path.isdir(d):
                names.update(g for g in os.listdir(d)
                             if g != "players"
                             and os.path.isdir(os.path.join(d, g)))
        for game_id in sorted(names):
            episodes = self.load_episodes(game_id)
            if episodes:
                result[game_id] = episodes
        return result

    def get_episode(self, episode_id: str) -> Optional[TeachingEpisode]:
        """Find a specific episode by ID across all games."""
        # Check in-memory first
        with self._lock:
            if episode_id in self._active:
                return self._active[episode_id]
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
