"""Environment-agnostic oversight protocols (the transferable-pilot seam).

``arc-witness-envs`` is the first adopter. A second team environment inherits
oversight by satisfying the subset of these protocols it can — they degrade
gracefully (an env with no ground truth still gets Snapshottable/Forkable).

Witness satisfies all four via the generic ``deepcopy(__dict__)`` mechanism
(snapshot/fork) plus the JSON-backed ``WitnessOracle`` and the arc_visualizer
renderer. The *snapshot precondition* for any candidate env: instance state
must be pure-Python and pickle-safe (no live handles/sockets/C-extension
state). An env that cannot meet it must supply its own capture/restore.
"""
from __future__ import annotations

from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class Snapshottable(Protocol):
    def snapshot(self, label: str = "") -> Any: ...
    def restore(self, snap: Any, verify: bool = False) -> None: ...


@runtime_checkable
class Forkable(Protocol):
    def fork(self) -> Any: ...
    def is_forked(self) -> bool: ...


@runtime_checkable
class Oracle(Protocol):
    def solution(self, game_id: str, level: int) -> Tuple[Optional[List[int]], Any]: ...
    def baseline(self, game_id: str, level: int, source: str = "bench") -> int: ...
    def rule_card(self, game_id: str) -> str: ...
    def state_value(self, snap: Any, rollouts: int = 64, seed: int = 0) -> Any: ...


@runtime_checkable
class Visualizable(Protocol):
    def render(self) -> Any: ...
