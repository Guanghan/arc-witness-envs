"""Snapshot / restore primitives over the bare ``ARCBaseGame``.

  snapshot()  = deepcopy(bare.__dict__) + defensive global-RNG capture + frame hash
  restore()   = in-place ``__dict__`` swap on the SAME bare object

**Why deepcopy, not pickle.** The locked architecture's primary mechanism is
``deepcopy(game.__dict__)``. We use it directly (in memory) rather than a
pickle blob because arcengine's ``GameAction`` enum does *not* round-trip
through pickle: members carry tuple values but reassign ``_value_`` in
``__init__``, so ``GameAction(0)`` is invalid (the SDK ships ``from_id`` /
``from_name`` for exactly this reason). A game's ``_action`` holds a
``GameAction``, so ``pickle.loads(pickle.dumps(game.__dict__))`` raises
``ValueError: 0 is not a valid GameAction``. ``deepcopy`` is unaffected (enum
members copy by identity). Pickle-to-disk persistence for the frozen *moment
library* (a later phase) therefore needs a custom ``GameAction`` reducer; the
in-memory snapshot/restore/fork primitives here do not.

The full ``__dict__`` is captured (not a field subset) because ``_levels`` is
the live list whose sprites mutate during play. Restore is done **in place**
(clear+update) so the bare object's identity is preserved — the SkyRL reward
path holds a direct reference and reads ``game._path`` off it
(agent_wrapper.py:256,323). Engine ``RESET`` is deliberately *not* used for
restore: ``full_reset``/``level_reset`` (base_game.py:305-329) only reach a
clean game/level start, never an arbitrary mid-trajectory state.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
import random
from typing import Any

try:  # numpy is an arcengine dependency, but stay defensive
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

from .resolve import resolve_root_game


class SnapshotError(Exception):
    """Base class for snapshot/restore failures."""


class SnapshotCaptureError(SnapshotError):
    """A game member could not be deep-copied (names the offending members)."""


class SnapshotVersionMismatch(SnapshotError):
    """Restore attempted across an arcengine version boundary."""


class RestoreVerificationError(SnapshotError):
    """Post-restore frame hash did not match the captured frame."""


def _arcengine_version() -> str:
    try:
        from importlib.metadata import version

        return version("arc-agi")
    except Exception:
        return "unknown"


def _frame_bytes(frame: Any) -> bytes:
    if _np is not None and isinstance(frame, _np.ndarray):
        return _np.ascontiguousarray(frame).tobytes()
    return repr(frame).encode("utf-8")


def _render_frame_hash(root: Any) -> str:
    frame = root.camera.render(root.current_level.get_sprites())
    return hashlib.sha256(_frame_bytes(frame)).hexdigest()


def _make_sid(game_id, level, score, action_count, state, frame_hash) -> str:
    key = f"{game_id}|{level}|{score}|{action_count}|{state}|{frame_hash}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True, eq=False)
class Snapshot:
    """An immutable, content-addressed capture of a bare game's full state.

    ``payload`` is an in-memory deepcopy of the bare game's ``__dict__``;
    ``sid`` is a content id over the visible/structural state. Restore
    deep-copies out of ``payload`` so the snapshot stays pristine for reuse.
    """

    game_id: str
    level_index: int
    score: int
    action_count: int
    state: str
    frame_hash: str
    sid: str
    arcengine_version: str
    payload: dict = field(repr=False)
    rng: Any = field(default=None, repr=False)
    label: str = ""
    schema_version: str = "1.1"

    def __repr__(self) -> str:
        return (
            f"Snapshot(game_id={self.game_id!r}, level={self.level_index}, "
            f"score={self.score}, state={self.state!r}, sid={self.sid[:12]}…)"
        )


def snapshot(game: Any, label: str = "") -> Snapshot:
    """Capture the full state of the bare game underneath ``game``."""
    root = resolve_root_game(game)
    try:
        payload = copy.deepcopy(root.__dict__)
    except Exception as e:  # locate the offending member(s)
        bad = []
        for k, v in root.__dict__.items():
            try:
                copy.deepcopy(v)
            except Exception:
                bad.append(k)
        raise SnapshotCaptureError(
            f"{getattr(root, '_game_id', '?')}: un-deepcopyable members {bad}: {e}"
        ) from e

    gid = getattr(root, "_game_id", getattr(root, "game_id", ""))
    level = root._current_level_index
    score = root._score
    action_count = root._action_count
    state = getattr(root._state, "value", str(root._state))
    frame_hash = _render_frame_hash(root)
    rng = (
        random.getstate(),
        _np.random.get_state() if _np is not None else None,
    )
    return Snapshot(
        game_id=gid,
        level_index=level,
        score=score,
        action_count=action_count,
        state=state,
        frame_hash=frame_hash,
        sid=_make_sid(gid, level, score, action_count, state, frame_hash),
        arcengine_version=_arcengine_version(),
        payload=payload,
        rng=rng,
        label=label,
    )


def restore(game: Any, snap: Snapshot, verify: bool = False) -> None:
    """Restore ``snap`` in place onto the bare game underneath ``game``."""
    root = resolve_root_game(game)
    if snap.arcengine_version != _arcengine_version():
        raise SnapshotVersionMismatch(
            f"snapshot taken on arcengine {snap.arcengine_version}, "
            f"current is {_arcengine_version()}"
        )
    if getattr(root, "_game_id", None) != snap.game_id:
        raise SnapshotError(
            f"game_id mismatch: snapshot {snap.game_id!r} vs game "
            f"{getattr(root, '_game_id', None)!r}"
        )

    # deepcopy OUT of the snapshot so it can be restored repeatedly without
    # aliasing the live game's mutable substructures.
    root.__dict__.clear()
    root.__dict__.update(copy.deepcopy(snap.payload))

    if snap.rng is not None:
        rstate, npstate = snap.rng
        random.setstate(rstate)
        if _np is not None and npstate is not None:
            _np.random.set_state(npstate)

    if verify:
        fh = _render_frame_hash(root)
        if fh != snap.frame_hash:
            raise RestoreVerificationError(
                f"{snap.game_id}: post-restore frame hash {fh[:12]}… != "
                f"captured {snap.frame_hash[:12]}…"
            )
