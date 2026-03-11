"""
FastAPI application entry point for the arc-witness OpenEnv server.

Usage:
    # Default: serve tw01
    uvicorn openenv_adapter.server.app:app --host 0.0.0.0 --port 8000

    # Specify game and reward mode via environment variables:
    WITNESS_GAME=tw03 WITNESS_REWARD=arc_score uvicorn openenv_adapter.server.app:app --port 8000
"""

import os

from openenv.core.env_server import create_app

from ..models import WitnessAction, WitnessObservation
from .witness_environment import WitnessEnvironment

# Configure via environment variables
_game_id = os.environ.get("WITNESS_GAME", "tw01")
_seed = int(os.environ.get("WITNESS_SEED", "0"))
_reward_mode = os.environ.get("WITNESS_REWARD", "shaped")


def _env_factory():
    return WitnessEnvironment(game_id=_game_id, seed=_seed, reward_mode=_reward_mode)


app = create_app(
    _env_factory,
    WitnessAction,
    WitnessObservation,
    env_name="arc_witness",
)


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
