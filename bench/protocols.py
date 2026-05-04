"""Agent protocol the benchmark expects.

Any object implementing `AgentProtocol.run_on_game()` can be evaluated by
`bench.runner.run_batch()`. Agents typically live outside this repo and
provide their own adapter that wraps their internal run-on-game logic
into an `AgentRunResult`.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from .types import AgentRunResult


@runtime_checkable
class AgentProtocol(Protocol):
    """What the eval runner needs from any agent.

    `game` is an opaque object exposing the witness env interface
    (`game.perform_action(ActionInput) -> FrameDataRaw`). The runner
    constructs `game` from `bench.catalog.load_game(game_id, seed)` before
    handing it off; agents do not need to know how it was made.
    """

    def run_on_game(
        self,
        game: Any,
        game_id: str,
        seed: int = 0,
        verbose: bool = False,
        max_levels: Optional[int] = None,
    ) -> AgentRunResult: ...
