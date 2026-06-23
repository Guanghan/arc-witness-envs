"""OversightEnv — the only oversight object that enters the bench stack.

It is a transparent inner wrapper around a bare ``ARCBaseGame`` and composes
*under* bench's ``_ResetCountingGame``:

    _ResetCountingGame(OversightEnv(bare))

``perform_action`` forwards verbatim (preserving the ``raw=`` flag and any
positional/keyword args); ``__getattr__`` forwards every other attribute, so
``game._path`` / ``game._grid`` survive both proxy layers (runner.py:60-62 and
the SkyRL reward read at agent_wrapper.py:323).

Snapshot/fork/oracle are reached as free functions over this object via
``resolve_root_game`` — OversightEnv itself stays a thin passthrough so that
removing this package leaves bench scoring byte-identical (the runner edit
falls back to identity when ``oversight`` is absent).
"""
from __future__ import annotations

from typing import Any

from .resolve import resolve_root_game


class OversightEnv:
    """Transparent passthrough wrapper around a bare ``ARCBaseGame``."""

    def __init__(self, game: Any) -> None:
        # Always wrap the truly-bare game, so resolving through an OversightEnv
        # is a single hop and double-wrapping is idempotent.
        self.__dict__["_bare"] = resolve_root_game(game)

    def perform_action(self, *args: Any, **kwargs: Any) -> Any:
        return self.__dict__["_bare"].perform_action(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        # __getattr__ only fires for attributes missing on the wrapper.
        if name == "_bare":
            raise AttributeError(name)
        return getattr(self.__dict__["_bare"], name)
