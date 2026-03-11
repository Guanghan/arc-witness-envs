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
    "tw01": ("environment_files.tw01.tw01", "Tw01"),
    "tw02": ("environment_files.tw02.tw02", "Tw02"),
    "tw03": ("environment_files.tw03.tw03", "Tw03"),
    "tw04": ("environment_files.tw04.tw04", "Tw04"),
    "tw05": ("environment_files.tw05.tw05", "Tw05"),
    "tw06": ("environment_files.tw06.tw06", "Tw06"),
    "tw07": ("environment_files.tw07.tw07", "Tw07"),
    "tw08": ("environment_files.tw08.tw08", "Tw08"),
    "tw09": ("environment_files.tw09.tw09", "Tw09"),
    "tw10": ("environment_files.tw10.tw10", "Tw10"),
    "tw11": ("environment_files.tw11.tw11", "Tw11"),
    "tw12": ("environment_files.tw12.tw12", "Tw12"),
    "tw13": ("environment_files.tw13.tw13", "Tw13"),
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

    Reward modes (reward_mode parameter):
    - "sparse": solve → +1.0, everything else → 0.0. Simplest signal,
      always non-negative, works with any RL algorithm.
    - "shaped": solve → +1.0, step → -0.01 (small constant penalty),
      wrong CONFIRM → -0.1. Solving is always net positive even at
      3× baseline steps. Encourages efficiency without drowning the
      solve signal.
    - "arc_score": solve → min(baseline/steps, 1.0) ∈ (0, 1].
      Directly mirrors ARC-AGI-3 scoring. No step penalty.
      Solve is always positive; efficiency gives higher reward.
    """

    def __init__(
        self,
        game_id: str = "tw01",
        seed: int = 0,
        max_steps_multiplier: int = 3,
        reward_mode: str = "shaped",
    ):
        super().__init__()
        if reward_mode not in ("sparse", "shaped", "arc_score"):
            raise ValueError(f"reward_mode must be 'sparse', 'shaped', or 'arc_score', got '{reward_mode}'")
        self._game_id = game_id
        self._seed = seed
        self._max_steps_multiplier = max_steps_multiplier
        self._reward_mode = reward_mode

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
        solved = curr_completed > prev_completed
        wrong_confirm = (action.action == WitnessGameAction.CONFIRM
                         and not solved)
        truncated = self._step_count >= self._max_steps()

        if solved:
            self._levels_completed = curr_completed
            self._level_index = curr_completed
            done = True
            message = f"Level solved! ({self._step_count} steps, baseline {baseline})"
        elif wrong_confirm:
            done = False
            message = "Wrong solution, try again."
        elif truncated:
            done = True
            message = f"Truncated at {self._step_count} steps (max {self._max_steps()})."
        else:
            done = False
            message = ""

        # Compute reward based on mode
        if self._reward_mode == "sparse":
            # Simplest: only reward on solve, always non-negative
            reward = 1.0 if solved else 0.0
        elif self._reward_mode == "shaped":
            # Solve is always net positive; small step penalty for efficiency
            if solved:
                reward = 1.0
            elif wrong_confirm:
                reward = -0.1
            else:
                reward = -0.01  # small constant, not scaled by baseline
        elif self._reward_mode == "arc_score":
            # Mirrors ARC-AGI-3 scoring: min(baseline/steps, 1.0)
            if solved:
                reward = min(baseline / self._step_count, 1.0)
            elif wrong_confirm:
                reward = -0.1
            else:
                reward = 0.0

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
