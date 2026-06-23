"""WitnessOracle — ground-truth access for the 13 witness games.

Almost free: ``levels/<game>_levels.json`` already ships an OPTIMAL,
CONFIRM-terminated ``solution_actions`` for every validated level, plus the
per-level optimal ``baseline``/``moves``; ``environment_files/<game>/
metadata.json`` ships the per-level scoring ``baseline_actions``. The IDDFS
solver in ``converters/validate.py`` can (re-)solve unvalidated levels offline.

The oracle is **read-only** w.r.t. scoring: it never touches
``WitnessGameInfo.baseline_actions`` (the scoring denominator, runner.py:127).
``state_value`` is **LLM-free** (seeded random rollouts on forks), so it is
safe to call inside an RL step.

Coverage is lumpy — be explicit, never hide it behind an aggregate:
  tw09/tw10 have NO solver (handcrafted examples only); tw12=4/160,
  tw03/tw11≈35%. ``solution()`` returns a typed ``SolutionStatus`` so callers
  know whether they hold proven-optimal truth, an example, or nothing.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple

from arcengine import ActionInput, GameAction

from .fork import fork
from .snapshot import Snapshot, restore

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_PKG_DIR)


class SolutionStatus(str, Enum):
    VALIDATED_OPTIMAL = "validated_optimal"      # solver-proven optimal
    HANDCRAFTED_EXAMPLE = "handcrafted_example"  # replays to WIN, not proven optimal (tw09/tw10)
    UNKNOWN = "unknown"                          # config-only level, no stored solution


@dataclass
class ValueEstimate:
    """Result of a fork-rollout state-value probe."""

    success_rate: float
    n_wins: int
    rollouts: int
    reachable: bool
    informative: bool
    optimal_moves: Optional[int]


class WitnessOracle:
    def __init__(self, repo_root: Optional[str] = None, loader: Optional[Callable] = None) -> None:
        self._root = repo_root or _REPO_ROOT
        self._loader = loader  # bench.catalog.load_game, imported lazily
        self._levels_cache: dict = {}
        self._meta_cache: dict = {}

    # ---- data access -----------------------------------------------------
    def _levels(self, game_id: str) -> List[dict]:
        if game_id not in self._levels_cache:
            path = os.path.join(self._root, "levels", f"{game_id}_levels.json")
            with open(path) as f:
                self._levels_cache[game_id] = json.load(f).get("levels", [])
        return self._levels_cache[game_id]

    def _meta(self, game_id: str) -> dict:
        if game_id not in self._meta_cache:
            path = os.path.join(self._root, "environment_files", game_id, "metadata.json")
            with open(path) as f:
                self._meta_cache[game_id] = json.load(f)
        return self._meta_cache[game_id]

    def _entry(self, game_id: str, level: int) -> dict:
        levels = self._levels(game_id)
        if not 0 <= level < len(levels):
            raise IndexError(f"{game_id}: level {level} out of range [0,{len(levels)})")
        return levels[level]

    # ---- ground-truth API ------------------------------------------------
    def solution(self, game_id: str, level: int) -> Tuple[Optional[List[int]], SolutionStatus]:
        """Return ``(solution_actions, status)`` for a level."""
        e = self._entry(game_id, level)
        sa = e.get("solution_actions")
        if not sa:
            return None, SolutionStatus.UNKNOWN
        status = (
            SolutionStatus.VALIDATED_OPTIMAL
            if e.get("validated")
            else SolutionStatus.HANDCRAFTED_EXAMPLE
        )
        return list(sa), status

    def baseline(self, game_id: str, level: int, source: str = "bench") -> int:
        """Per-level baseline. ``source='bench'`` -> the scoring budget from
        metadata.json; ``source='optimal'`` -> the optimal-derived value in the
        levels JSON. Never feeds the scorer either way (read-only)."""
        if source == "bench":
            ba = self._meta(game_id).get("baseline_actions", [])
            if 0 <= level < len(ba):
                return int(ba[level])
            return int(self._entry(game_id, level).get("baseline", 0))
        if source == "optimal":
            return int(self._entry(game_id, level).get("baseline", 0))
        raise ValueError(f"unknown baseline source {source!r}")

    def optimal_moves(self, game_id: str, level: int) -> Optional[int]:
        v = self._entry(game_id, level).get("moves")
        return int(v) if v is not None else None

    def rule_card(self, game_id: str) -> str:
        """Hand-written ground-truth rules for a game (empty if none)."""
        path = os.path.join(_PKG_DIR, "rule_cards", f"{game_id}.md")
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return ""

    def coverage(self) -> dict:
        """Per-game validated/handcrafted/total counts."""
        out = {}
        for game_id in sorted(self._game_ids()):
            levels = self._levels(game_id)
            validated = sum(1 for L in levels if L.get("validated") and L.get("solution_actions"))
            handcrafted = sum(
                1 for L in levels if not L.get("validated") and L.get("solution_actions")
            )
            out[game_id] = {
                "validated": validated,
                "handcrafted": handcrafted,
                "total": len(levels),
            }
        return out

    def _game_ids(self) -> List[str]:
        return [f"tw{i:02d}" for i in range(1, 14)]

    def solve_now(self, game_id: str, level: int, timeout: float = 10.0) -> Optional[List[int]]:
        """Re-solve a level with the IDDFS solver (tw01-08,11,12,13 only).

        Returns a CONFIRM-terminated action list, or None if unsolved / no
        solver (tw09/tw10). This is the per-level unit of the offline batch
        re-solve that lifts coverage on tw03/tw11/tw12 before oracle use."""
        from converters.validate import solution_to_actions, validate_config

        cfg = self._entry(game_id, level).get("config", {})
        res = validate_config(cfg, game_id, timeout=timeout)
        if not res.get("valid") or res.get("solution") is None:
            return None
        return solution_to_actions(res["solution"])

    def state_value(
        self,
        snap: Snapshot,
        rollouts: int = 64,
        seed: int = 0,
        horizon: Optional[int] = None,
    ) -> ValueEstimate:
        """LLM-free fork-rollout value estimate from a snapshot.

        Plays seeded random actions (1-5) on independent forks, honoring
        multi-start auto-select and breakpoints (it drives ``perform_action``,
        which enforces both). Reports ``informative=False`` when no rollout
        wins — hard region-constraint games (tw07/tw11/tw13) read ~0, which is
        an honest 'uninformative' rather than a misleading 0."""
        if self._loader is None:
            from bench.catalog import load_game

            self._loader = load_game

        base = self._loader(snap.game_id, 0)
        restore(base, snap)
        om = self.optimal_moves(snap.game_id, snap.level_index)
        if horizon is None:
            horizon = 4 * om if om else 50

        rng = random.Random(seed)
        n_wins = 0
        for _ in range(rollouts):
            child = fork(base)
            start_score = child._score
            for _step in range(horizon):
                a = rng.randint(1, 5)
                fd = child.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
                st = getattr(fd.state, "value", str(fd.state))
                if fd.levels_completed > start_score or st == "WIN":
                    n_wins += 1
                    break
                if st == "GAME_OVER":
                    break

        sr = (n_wins / rollouts) if rollouts else 0.0
        return ValueEstimate(
            success_rate=sr,
            n_wins=n_wins,
            rollouts=rollouts,
            reachable=n_wins > 0,
            informative=n_wins > 0,
            optimal_moves=om,
        )
