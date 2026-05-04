"""Game catalog — owned by the benchmark, not the agent.

Provides the canonical mapping from game_id to game class plus loaders for
metadata (`WitnessGameInfo`) and game instances. The agent repo now
delegates to these helpers instead of carrying its own GAME_CLASSES dict.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .types import WitnessGameInfo


# Repo root = directory containing this file's parent (bench/) parent.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_FILES = os.path.join(_REPO_ROOT, "environment_files")
_LEVELS_DIR = os.path.join(_REPO_ROOT, "levels")


# Make `from environment_files.tw01.tw01 import Tw01` work without forcing
# callers to mess with sys.path themselves.
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


GAME_CLASSES: Dict[str, Tuple[str, str]] = {
    f"tw{i:02d}": (f"environment_files.tw{i:02d}.tw{i:02d}", f"Tw{i:02d}")
    for i in range(1, 14)
}


def list_games() -> List[str]:
    """Return all benchmark game_ids in canonical order."""
    return sorted(GAME_CLASSES.keys())


def load_game_info(game_id: str) -> WitnessGameInfo:
    """Load static benchmark metadata for a game.

    Reads `environment_files/<game_id>/metadata.json` for tags and
    `baseline_actions`, and `levels/<game_id>_levels.json` for the real
    total level count (which can exceed `len(baseline_actions)`).
    """
    if game_id not in GAME_CLASSES:
        raise ValueError(
            f"Unknown witness game: {game_id!r}. Available: {list_games()}"
        )

    meta_path = os.path.join(_ENV_FILES, game_id, "metadata.json")
    with open(meta_path) as f:
        meta = json.load(f)

    levels_path = os.path.join(_LEVELS_DIR, f"{game_id}_levels.json")
    real_total = 0
    if os.path.exists(levels_path):
        with open(levels_path) as f:
            real_total = len(json.load(f).get("levels", []))

    date_dl = meta.get("date_downloaded")
    parsed_date = None
    if date_dl:
        try:
            parsed_date = datetime.fromisoformat(date_dl.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            parsed_date = None

    return WitnessGameInfo(
        game_id=meta["game_id"],
        title=meta.get("title"),
        class_name=meta.get("class_name"),
        tags=meta.get("tags"),
        private_tags=meta.get("private_tags"),
        level_tags=meta.get("level_tags"),
        baseline_actions=list(meta.get("baseline_actions", [])),
        real_total_levels=real_total,
        date_downloaded=parsed_date,
    )


def load_game(game_id: str, seed: int = 0) -> Any:
    """Instantiate a game object exposing the witness env interface
    (`game.perform_action(ActionInput) -> FrameDataRaw`)."""
    if game_id not in GAME_CLASSES:
        raise ValueError(
            f"Unknown witness game: {game_id!r}. Available: {list_games()}"
        )
    module_name, class_name = GAME_CLASSES[game_id]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(seed=seed)
