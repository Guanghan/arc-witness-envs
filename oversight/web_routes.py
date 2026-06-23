"""Optional interactive oversight HTTP routes for play_human (OPT-IN).

``register_oversight_routes(app)`` adds ``/api/oversight/*`` endpoints that
load / step / snapshot / restore / fork a *server-side oversight game* (via
bench.catalog), independent of the SDK play env. This is an analyst surface,
not the human-play path.

OFF by default — play_human registers these only when
``WITNESS_OVERSIGHT_ROUTES=1`` (Decision #4: don't widen the public HTTP
surface near the Kaggle inference boundary unless explicitly wanted). Flask is
imported lazily so the oversight package stays import-light.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .fork import fork as _fork
from .resolve import resolve_root_game
from .snapshot import Snapshot
from .snapshot import restore as _restore
from .snapshot import snapshot as _snapshot


class _Registry:
    """In-process oversight sessions: session_id -> game, sid -> Snapshot."""

    def __init__(self) -> None:
        self.games: Dict[str, Any] = {}
        self.snaps: Dict[str, Snapshot] = {}
        self._n = 0

    def new_session(self, game: Any) -> str:
        self._n += 1
        sess = f"sess{self._n}"
        self.games[sess] = game
        return sess


def register_oversight_routes(app: Any, registry: Optional[_Registry] = None) -> _Registry:
    """Attach /api/oversight/* routes to a Flask app. Returns the registry."""
    import numpy as np
    from flask import jsonify, request

    from arcengine import ActionInput, GameAction
    from bench.catalog import load_game

    reg = registry or _Registry()

    def _frame(game: Any) -> Dict[str, Any]:
        root = resolve_root_game(game)
        arr = root.camera.render(root.current_level.get_sprites())
        snap = _snapshot(game)  # also gives the frame_hash for this state
        return {
            "level": root._current_level_index,
            "score": root._score,
            "state": getattr(root._state, "value", str(root._state)),
            "frame_hash": snap.frame_hash,
            "grid": np.asarray(arr, dtype=int).tolist(),
        }

    @app.route("/api/oversight/load", methods=["POST"])
    def ov_load():
        b = request.get_json(force=True) or {}
        gid = b.get("game_id")
        if not gid:
            return jsonify({"error": "missing game_id"}), 400
        try:
            game = load_game(gid, int(b.get("seed", 0)))
        except Exception as e:
            return jsonify({"error": f"{type(e).__name__}: {e}"}), 404
        sess = reg.new_session(game)
        return jsonify({"session": sess, "game_id": gid, **_frame(game)})

    @app.route("/api/oversight/step", methods=["POST"])
    def ov_step():
        b = request.get_json(force=True) or {}
        game = reg.games.get(b.get("session"))
        if game is None:
            return jsonify({"error": "unknown session"}), 404
        game.perform_action(ActionInput(id=GameAction.from_id(int(b.get("action", 0)))))
        return jsonify({"session": b.get("session"), **_frame(game)})

    @app.route("/api/oversight/snapshot", methods=["POST"])
    def ov_snapshot():
        b = request.get_json(force=True) or {}
        game = reg.games.get(b.get("session"))
        if game is None:
            return jsonify({"error": "unknown session"}), 404
        snap = _snapshot(game, label=b.get("label", ""))
        reg.snaps[snap.sid] = snap
        return jsonify({"session": b.get("session"), "sid": snap.sid,
                        "level": snap.level_index, "score": snap.score})

    @app.route("/api/oversight/restore", methods=["POST"])
    def ov_restore():
        b = request.get_json(force=True) or {}
        game = reg.games.get(b.get("session"))
        snap = reg.snaps.get(b.get("sid"))
        if game is None:
            return jsonify({"error": "unknown session"}), 404
        if snap is None:
            return jsonify({"error": "unknown sid"}), 404
        _restore(game, snap)
        return jsonify({"session": b.get("session"), **_frame(game)})

    @app.route("/api/oversight/fork", methods=["POST"])
    def ov_fork():
        b = request.get_json(force=True) or {}
        game = reg.games.get(b.get("session"))
        if game is None:
            return jsonify({"error": "unknown session"}), 404
        child = _fork(game)
        csess = reg.new_session(child)
        return jsonify({"session": csess, "forked_from": b.get("session"), **_frame(child)})

    return reg
