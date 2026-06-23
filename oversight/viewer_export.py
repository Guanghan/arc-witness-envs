"""viewer_export — produce a self-contained multi-trajectory replay artifact.

A "tree" = a trunk trajectory plus any number of fork branches (counter-factual
retries from a branch point) plus an optional oracle ghost (the level's optimal
solution). Each trajectory is rendered by replaying actions on an isolated
``fork`` of the base game, so producing the artifact never mutates anything and
needs no live agent.

Output (schema 3.0 — same shape arc_visualizer/build_tree emits, so the
arc_visualizer tree.html/tree.js viewer renders it directly):
  <out_dir>/tree.json     manifest with ``trajectories[]``
  <out_dir>/frames.bin    packed uint8, ``n_frames * 64 * 64`` (row-major)

This is deliberately self-contained — it packs the frames the engine already
renders (raw=True), so it does NOT import arc_visualizer. The arc_visualizer
viewer is the *consumer* of this artifact (the trajectory-tree / compare /
oracle-overlay UI); building the artifact does not depend on it.
"""
from __future__ import annotations

import json
import os
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

from .fork import _to_action, fork
from .snapshot import restore, snapshot

GRID = 64


def _step_frames(game, actions) -> Tuple[List[np.ndarray], List[int], List[str]]:
    """Replay actions, capturing one settled 64x64 frame + outcome per action."""
    frames: List[np.ndarray] = []
    lcs: List[int] = []
    states: List[str] = []
    last: Optional[np.ndarray] = None
    for a in actions:
        fd = game.perform_action(_to_action(a), raw=True)
        subs = fd.frame
        if subs:
            arr = np.asarray(subs[-1], dtype=np.uint8)
            last = arr
        elif last is not None:
            arr = last  # terminal state renders no new frame; hold the last
        else:
            arr = np.zeros((GRID, GRID), dtype=np.uint8)
        frames.append(arr)
        lcs.append(int(fd.levels_completed))
        states.append(getattr(fd.state, "value", str(fd.state)))
    return frames, lcs, states


def export_tree(
    out_dir: str,
    game_id: str,
    seed: int,
    trunk_actions: Sequence[int],
    branches: Optional[Sequence[Tuple[int, Sequence[int], str]]] = None,
    oracle_actions: Optional[Sequence[int]] = None,
    loader: Optional[Any] = None,
) -> dict:
    """Build a schema-3.0 trajectory-tree artifact.

    branches: list of ``(branch_point_frame, actions, label)`` — each forks the
    trunk state after ``branch_point_frame`` trunk actions, then replays
    ``actions`` (the counter-factual). oracle_actions: optional ghost overlay.
    """
    os.makedirs(out_dir, exist_ok=True)
    if loader is None:
        from bench.catalog import load_game

        loader = load_game
    base = loader(game_id, seed)

    trajectories: List[dict] = []
    all_frames: List[np.ndarray] = []

    def _add(label, kind, actions, parent_id, branch_point, from_snapshot):
        child = fork(base)
        if from_snapshot is not None:
            restore(child, from_snapshot)
        frames, lcs, states = _step_frames(child, actions)
        start = len(all_frames)
        all_frames.extend(frames)
        trajectories.append(
            {
                "id": label,
                "kind": kind,
                "parent_id": parent_id,
                "branch_point_frame": int(branch_point),
                "frame_start": start,
                "n_frames": len(frames),
                "actions": [int(a) for a in actions],
                "levels_completed": lcs,
                "states": states,
                "solved": bool(lcs and lcs[-1] > lcs[0]),
                "label": label,
            }
        )

    _add("trunk", "trunk", list(trunk_actions), None, 0, None)

    for i, (bp, b_actions, blabel) in enumerate(branches or []):
        # snapshot the trunk state after `bp` trunk actions (on a throwaway fork)
        tmp = fork(base)
        for n in list(trunk_actions)[:bp]:
            tmp.perform_action(_to_action(n), raw=True)
        snap = snapshot(tmp, label=f"branch_point_{bp}")
        _add(blabel or f"fork{i}", "fork", list(b_actions), "trunk", bp, snap)

    if oracle_actions:
        _add("oracle", "oracle", list(oracle_actions), "trunk", 0, None)

    if all_frames:
        arr = np.stack(all_frames).astype(np.uint8)
    else:
        arr = np.zeros((0, GRID, GRID), dtype=np.uint8)
    arr.tofile(os.path.join(out_dir, "frames.bin"))

    manifest = {
        "schema_version": "3.0",
        "kind": "tree",
        "game_id": game_id,
        "short_id": game_id.split("-", 1)[0],
        "seed": seed,
        "grid": {"h": GRID, "w": GRID},
        "frames_url": "frames.bin",
        "frames_dtype": "uint8",
        "n_frames": int(arr.shape[0]),
        "trajectories": trajectories,
    }
    with open(os.path.join(out_dir, "tree.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest
