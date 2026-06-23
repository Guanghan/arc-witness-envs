"""Counter-factual fork / branch primitives.

``fork`` deepcopies the bare game into an independent object and marks it
forked via a module-level ``WeakSet`` — the forked flag lives **off** the
game's ``__dict__`` (decision L9), so snapshotting a fork never carries the
flag into the blob, and restoring a fork's state onto a live scored game can
never silently mark it forked.

``branch`` runs an action list on a *fork* of the live game (optionally after
restoring a snapshot), so the live trajectory is never mutated. A branch's
output has the same ``(frames, levels_completed, states)`` shape the
visualizer's ``engine.replay`` produces, so a branch is a viewer trajectory
with no new render path.
"""
from __future__ import annotations

import copy
import weakref
from dataclasses import dataclass, field
from typing import Any, List, Optional

from arcengine import ActionInput, GameAction

from .resolve import resolve_root_game
from .snapshot import Snapshot, restore as _restore

# Identity set of forked bare games. WeakSet so forks are GC'd normally.
_FORKED: "weakref.WeakSet[Any]" = weakref.WeakSet()


def fork(game: Any) -> Any:
    """Return an independent deepcopy of the bare game underneath ``game``."""
    root = resolve_root_game(game)
    child = copy.deepcopy(root)
    _FORKED.add(child)
    return child


def is_forked(game: Any) -> bool:
    """True iff the bare game underneath ``game`` was produced by ``fork``."""
    try:
        root = resolve_root_game(game)
    except TypeError:
        return False
    return root in _FORKED


def _to_action(a: Any) -> ActionInput:
    if isinstance(a, ActionInput):
        return a
    if isinstance(a, GameAction):
        return ActionInput(id=a)
    return ActionInput(id=GameAction.from_id(int(a)))


@dataclass
class BranchResult:
    """Frames + outcome of replaying actions on a fork."""

    frames: List[Any] = field(default_factory=list)
    levels_completed: List[int] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    final_state: str = ""
    final_levels_completed: int = 0


def branch(
    game: Any,
    actions: List[Any],
    from_snapshot: Optional[Snapshot] = None,
    raw: bool = True,
) -> BranchResult:
    """Replay ``actions`` on a fork of ``game`` (optionally restoring a
    snapshot first). The live ``game`` is never mutated."""
    child = fork(game)
    if from_snapshot is not None:
        _restore(child, from_snapshot)

    res = BranchResult()
    for a in actions:
        fd = child.perform_action(_to_action(a), raw=raw)
        res.frames.append(fd.frame)
        res.levels_completed.append(fd.levels_completed)
        res.states.append(getattr(fd.state, "value", str(fd.state)))

    res.final_state = res.states[-1] if res.states else getattr(
        resolve_root_game(child)._state, "value", ""
    )
    res.final_levels_completed = (
        res.levels_completed[-1] if res.levels_completed else resolve_root_game(child)._score
    )
    return res
