"""
OpenEnv Environment wrapper for arc-witness games.

Wraps any ARCBaseGame subclass (Tw01-Tw13) into the OpenEnv Environment
protocol, treating each level as one RL episode.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Dict, List, Optional, Type

import numpy as np
from openenv.core.env_server import Environment
from openenv.core.env_server.types import State

from arcengine import ActionInput, GameAction

# Ensure repo root is importable
_repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from ..models import WitnessAction, WitnessGameAction, WitnessObservation

# Map string actions to arcengine GameAction
_ACTION_MAP: Dict[WitnessGameAction, GameAction] = {
    WitnessGameAction.UP: GameAction.ACTION1,
    WitnessGameAction.DOWN: GameAction.ACTION2,
    WitnessGameAction.LEFT: GameAction.ACTION3,
    WitnessGameAction.RIGHT: GameAction.ACTION4,
    WitnessGameAction.CONFIRM: GameAction.ACTION5,
}

# All known game classes and their modules
_GAME_REGISTRY: Dict[str, tuple] = {
    "tw01": ("tw01_pathdots", "Tw01"),
    "tw02": ("tw02_colorsplit", "Tw02"),
    "tw03": ("tw03_shapefill", "Tw03"),
    "tw04": ("tw04_symdraw", "Tw04"),
    "tw05": ("tw05_starpair", "Tw05"),
    "tw06": ("tw06_tricount", "Tw06"),
    "tw07": ("tw07_eraserlogic", "Tw07"),
    "tw08": ("tw08_combobasic", "Tw08"),
    "tw09": ("tw09_cylinderwrap", "Tw09"),
    "tw10": ("tw10_colorfilter", "Tw10"),
    "tw11": ("tw11_multiregion", "Tw11"),
    "tw12": ("tw12_hexcombo", "Tw12"),
    "tw13": ("tw13_eraserall", "Tw13"),
}


def _load_game_class(game_id: str):
    """Dynamically import and return the ARCBaseGame subclass for a game."""
    if game_id not in _GAME_REGISTRY:
        raise ValueError(f"Unknown game_id: {game_id}. Available: {list(_GAME_REGISTRY)}")
    module_name, class_name = _GAME_REGISTRY[game_id]
    import importlib
    mod = importlib.import_module(module_name)
    return getattr(mod, class_name)


def _load_baselines(game_id: str) -> List[int]:
    """Load baseline action counts from metadata.json."""
    meta_path = os.path.join(_repo_root, "environment_files", game_id, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        return meta.get("baseline_actions", [])
    return []


class WitnessEnvironment(Environment):
    """
    OpenEnv Environment wrapping an ARC-AGI-3 Witness game.

    Episode granularity: one level per episode.
    - reset(): starts (or restarts) the current level
    - step(): executes one game action, returns observation with shaped reward
    - Automatically advances to next level when current level is solved

    Reward shaping:
    - Each step: -1 / baseline_actions (penalize inefficiency)
    - CONFIRM success (level solved): +1.0
    - CONFIRM failure (wrong solution): -0.5
    - Episode truncation: max_steps = baseline × 3
    """

    def __init__(
        self,
        game_id: str = "tw01",
        seed: int = 0,
        max_steps_multiplier: int = 3,
    ):
        super().__init__()
        self._game_id = game_id
        self._seed = seed
        self._max_steps_multiplier = max_steps_multiplier

        # Load game
        game_cls = _load_game_class(game_id)
        self._game = game_cls(seed=seed)

        # Load baselines
        self._baselines = _load_baselines(game_id)
        self._total_levels = len(self._baselines) if self._baselines else self._game._win_score

        # Episode state
        self._level_index = 0
        self._step_count = 0
        self._levels_completed = 0
        self._state = State(episode_id=str(uuid.uuid4()), step_count=0)

        # Initialize game with RESET
        self._last_frame = self._game.perform_action(
            ActionInput(id=GameAction.RESET), raw=True
        )

    @property
    def state(self) -> State:
        return self._state

    def _baseline_for_level(self) -> int:
        """Get baseline action count for current level."""
        if self._level_index < len(self._baselines):
            return self._baselines[self._level_index]
        return 30  # fallback default

    def _max_steps(self) -> int:
        return self._baseline_for_level() * self._max_steps_multiplier

    def _frame_to_grid(self, frame) -> List[List[int]]:
        """Convert FrameDataRaw.frame to 64x64 list of lists."""
        if frame and frame.frame:
            arr = frame.frame[0]  # first (and usually only) layer
            if isinstance(arr, np.ndarray):
                return arr.tolist()
        return [[0] * 64 for _ in range(64)]

    def _make_obs(
        self, reward: float = 0.0, done: bool = False, message: str = ""
    ) -> WitnessObservation:
        return WitnessObservation(
            frame=self._frame_to_grid(self._last_frame),
            level_index=self._level_index,
            levels_completed=self._levels_completed,
            total_levels=self._total_levels,
            available_actions=(
                self._last_frame.available_actions
                if self._last_frame else [1, 2, 3, 4, 5]
            ),
            message=message,
            reward=reward,
            done=done,
        )

    def reset(self, seed: Optional[int] = None, **kwargs) -> WitnessObservation:
        """Reset the current level (episode)."""
        if seed is not None:
            self._seed = seed

        self._step_count = 0
        self._state = State(episode_id=str(uuid.uuid4()), step_count=0)

        # Reset the game to replay current level
        self._last_frame = self._game.perform_action(
            ActionInput(id=GameAction.RESET), raw=True
        )

        return self._make_obs(
            reward=0.0, done=False,
            message=f"Level {self._level_index}/{self._total_levels}"
        )

    def step(self, action: WitnessAction, **kwargs) -> WitnessObservation:
        """Execute one action and return observation with shaped reward."""
        self._step_count += 1
        self._state.step_count = self._step_count

        game_action = _ACTION_MAP[action.action]
        prev_completed = self._last_frame.levels_completed if self._last_frame else 0

        # Execute action
        self._last_frame = self._game.perform_action(
            ActionInput(id=game_action), raw=True
        )

        curr_completed = self._last_frame.levels_completed if self._last_frame else 0
        baseline = self._baseline_for_level()

        # Determine reward and done
        if curr_completed > prev_completed:
            # Level solved
            reward = 1.0
            self._levels_completed = curr_completed
            self._level_index = curr_completed
            done = True
            message = f"Level solved! ({self._step_count} steps, baseline {baseline})"
        elif (action.action == WitnessGameAction.CONFIRM
              and curr_completed == prev_completed):
            # CONFIRM but level not solved (wrong solution)
            reward = -0.5
            done = False
            message = "Wrong solution, try again."
        elif self._step_count >= self._max_steps():
            # Truncated
            reward = -1.0 / baseline
            done = True
            message = f"Truncated at {self._step_count} steps (max {self._max_steps()})."
        else:
            # Normal step
            reward = -1.0 / baseline
            done = False
            message = ""

        return self._make_obs(reward=reward, done=done, message=message)

    def set_level(self, level_index: int) -> WitnessObservation:
        """Jump to a specific level (non-standard, useful for curriculum)."""
        self._level_index = level_index
        self._step_count = 0
        self._state = State(episode_id=str(uuid.uuid4()), step_count=0)

        # Reset game fully, then advance to target level
        self._last_frame = self._game.perform_action(
            ActionInput(id=GameAction.RESET), raw=True
        )

        return self._make_obs(
            reward=0.0, done=False,
            message=f"Set to level {level_index}/{self._total_levels}"
        )

    def close(self) -> None:
        """Clean up resources."""
        pass


def create_witness_environment(game_id: str = "tw01", seed: int = 0):
    """Factory function for create_app — returns a callable that creates the env."""
    def _factory():
        return WitnessEnvironment(game_id=game_id, seed=seed)
    return _factory
