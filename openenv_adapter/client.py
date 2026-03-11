"""
OpenEnv client for connecting to an arc-witness environment server.

Usage:
    import asyncio
    from openenv_adapter.client import WitnessEnvClient
    from openenv_adapter.models import WitnessAction, WitnessGameAction

    async def main():
        client = WitnessEnvClient(base_url="ws://localhost:8000")
        async with client:
            result = await client.reset()
            print(f"Initial frame shape: {len(result.observation.frame)}x{len(result.observation.frame[0])}")

            result = await client.step(WitnessAction(action=WitnessGameAction.RIGHT))
            print(f"Reward: {result.reward}, Done: {result.done}")

    asyncio.run(main())
"""

from __future__ import annotations

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient
from openenv.core.env_server.types import State

from .models import WitnessAction, WitnessGameAction, WitnessObservation


class WitnessEnvClient(EnvClient[WitnessAction, WitnessObservation, State]):
    """WebSocket client for the arc-witness OpenEnv server."""

    def step_action(self, action: WitnessGameAction) -> StepResult[WitnessObservation]:
        """Helper to send a game action by enum value."""
        return super().step(WitnessAction(action=action))

    def _step_payload(self, action: WitnessAction) -> dict:
        """Serialize action to dict for WebSocket transmission."""
        return action.model_dump()

    def _parse_result(self, data: dict) -> StepResult[WitnessObservation]:
        """Deserialize server response into typed StepResult."""
        return StepResult(
            observation=WitnessObservation(**data["observation"]),
            reward=data["reward"],
            done=data["done"],
            info=data.get("info", {}),
        )

    def _parse_state(self, data: dict) -> State:
        """Deserialize state response."""
        return State(**data)
