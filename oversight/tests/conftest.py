"""Shared fixtures/helpers for oversight tests.

Puts the repo root on sys.path (so ``import bench``, ``import oversight``,
``from environment_files...`` all resolve) exactly the way bench.catalog does.
"""
import json
import os
import sys

# oversight/tests/conftest.py -> oversight/tests -> oversight -> <repo root>
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import hashlib  # noqa: E402

from arcengine import ActionInput, GameAction  # noqa: E402
from bench.catalog import list_games, load_game  # noqa: E402

ALL_GAMES = list_games()
_LEVELS_DIR = os.path.join(_REPO_ROOT, "levels")


def ai(n):
    """Build an ActionInput from an int id (0=RESET, 1-5 = UP/DOWN/LEFT/RIGHT/CONFIRM)."""
    return ActionInput(id=GameAction.from_id(int(n)))


def digest(game, actions):
    """Stable hash of the frame stream + per-action outcome for an action list.

    Works on a bare game *or* any proxy whose ``perform_action`` takes a single
    positional ActionInput (e.g. ``_ResetCountingGame``).
    """
    h = hashlib.sha256()
    for n in actions:
        fd = game.perform_action(ai(n))
        h.update(repr(fd.frame).encode())
        h.update(f"|{fd.levels_completed}|{getattr(fd.state, 'value', fd.state)}\n".encode())
    return h.hexdigest()

# Generic fallback move sequence (UP/DOWN/LEFT/RIGHT) for games whose first
# level has no stored solution. Enough to mutate path state deterministically.
_FALLBACK = [4, 2, 3, 1, 4, 4, 2]


def first_solution(game_id, max_len=24):
    """Return the first stored solution_actions for a game, truncated.

    Solving level 0 advances the level (exercising on_set_level + level
    bookkeeping), so this is a stronger snapshot exercise than raw moves.
    """
    path = os.path.join(_LEVELS_DIR, f"{game_id}_levels.json")
    try:
        with open(path) as f:
            data = json.load(f)
        for lv in data.get("levels", []):
            sa = lv.get("solution_actions")
            if sa:
                return list(sa)[:max_len]
    except (OSError, ValueError):
        pass
    return list(_FALLBACK)
