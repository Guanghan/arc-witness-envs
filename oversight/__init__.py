"""arc-witness-envs oversight toolbox — agent-agnostic, import-optional.

Engine-level oversight primitives over the bare arcengine ``ARCBaseGame``:
snapshot / restore / fork / branch, plus the ``OversightEnv`` passthrough that
composes safely under bench scoring. Nothing here is imported by the Kaggle /
gateway inference path; the package is removable with byte-identical bench
scoring (bench/runner.py falls back to identity when this package is absent).

Agent-coupled features (inject_rules, percept overlay, discipline,
RolloutController, trace provenance) live in ``arc-witness-agent/oversight/``
and *import* these primitives.
"""
from __future__ import annotations

from .resolve import resolve_root_game, register_unwrap
from .snapshot import (
    Snapshot,
    snapshot,
    restore,
    SnapshotError,
    SnapshotCaptureError,
    SnapshotVersionMismatch,
    RestoreVerificationError,
)
from .fork import fork, is_forked, branch, BranchResult
from .env import OversightEnv
from .oracle import WitnessOracle, SolutionStatus, ValueEstimate
from .viewer_export import export_tree

__all__ = [
    "resolve_root_game",
    "register_unwrap",
    "Snapshot",
    "snapshot",
    "restore",
    "SnapshotError",
    "SnapshotCaptureError",
    "SnapshotVersionMismatch",
    "RestoreVerificationError",
    "fork",
    "is_forked",
    "branch",
    "BranchResult",
    "OversightEnv",
    "WitnessOracle",
    "SolutionStatus",
    "ValueEstimate",
    "export_tree",
]
