"""resolve_root_game — the single chokepoint that unwraps any wrapper stack
down to the bare arcengine ``ARCBaseGame``.

Every oversight primitive operates on the bare game so that bench's
``_ResetCountingGame`` reset counters (runner.py:37-62) and the SDK's
``ScorecardManager`` (``arc_agi/scorecard.py``) are *structurally* excluded
from snapshots — the bare arcengine game holds a reference to neither.

Unwrap chain (verified):
  - ``OversightEnv._bare``                       (this package, env.py)
  - ``_ResetCountingGame._game``                 (bench/runner.py:48)
  - ``ArcSDKAdapter._env`` -> ``LocalEnvironmentWrapper._game``  (agent + SDK)
A second (non-witness) environment can declare its own unwrap via
``register_unwrap`` — the resolver is not hard-wired to witness/SDK.
"""
from __future__ import annotations

from typing import Any, Callable, List, Tuple

from arcengine import ARCBaseGame

# (predicate, getter) hooks consulted before the default attribute chain.
_UNWRAP_HOOKS: List[Tuple[Callable[[Any], bool], Callable[[Any], Any]]] = []

# Attribute names that hold an inner wrapped object, in priority order.
_UNWRAP_ATTRS = ("_bare", "_game", "_env")


def register_unwrap(predicate: Callable[[Any], bool], getter: Callable[[Any], Any]) -> None:
    """Register how a non-witness wrapper unwraps toward the bare game.

    ``predicate(obj)`` selects the wrapper type; ``getter(obj)`` returns the
    next inner object. Hooks are tried before the default ``_UNWRAP_ATTRS``.
    """
    _UNWRAP_HOOKS.append((predicate, getter))


def resolve_root_game(obj: Any) -> ARCBaseGame:
    """Return the bare ``ARCBaseGame`` underneath any stack of wrappers."""
    seen: set[int] = set()
    while not isinstance(obj, ARCBaseGame):
        if id(obj) in seen:
            raise TypeError(
                f"resolve_root_game: cycle while unwrapping {type(obj).__name__}"
            )
        seen.add(id(obj))

        nxt = None
        for pred, getter in _UNWRAP_HOOKS:
            try:
                if pred(obj):
                    nxt = getter(obj)
                    break
            except Exception:
                continue
        if nxt is None:
            for attr in _UNWRAP_ATTRS:
                cand = getattr(obj, attr, None)
                if cand is not None and cand is not obj:
                    nxt = cand
                    break
        if nxt is None:
            raise TypeError(
                f"resolve_root_game: cannot unwrap {type(obj).__name__} to ARCBaseGame"
            )
        obj = nxt
    return obj
