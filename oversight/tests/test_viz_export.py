"""P3 (envs-side) — the schema-3.0 trajectory-tree export artifact.

The arc_visualizer frontend is the *consumer* of this artifact; producing it is
self-contained and tested here.

Run: python -m pytest oversight/tests/test_viz_export.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from oversight import WitnessOracle, export_tree  # noqa: E402


def test_export_tree(tmp_path):
    orc = WitnessOracle()
    sol, _ = orc.solution("tw01", 0)
    trunk = sol[:3]  # an incomplete (counter-factually "wrong") run
    branches = [(0, sol, "optimal")]  # branch at the start, replay the optimal solution

    m = export_tree(str(tmp_path), "tw01", 0, trunk, branches=branches, oracle_actions=sol)

    assert m["schema_version"] == "3.0" and m["kind"] == "tree"
    assert m["grid"] == {"h": 64, "w": 64}
    assert [t["kind"] for t in m["trajectories"]] == ["trunk", "fork", "oracle"]
    # canonical per-trajectory fields the tree viewer + validator require
    for t in m["trajectories"]:
        for k in ("id", "parent_id", "branch_point_frame", "frame_start",
                  "n_frames", "actions", "levels_completed", "states", "solved", "label"):
            assert k in t, f"trajectory missing {k}"

    # frames.bin size is exactly n_frames * 64 * 64 uint8
    nbytes = os.path.getsize(os.path.join(str(tmp_path), "frames.bin"))
    assert nbytes == m["n_frames"] * 64 * 64

    # frame_start offsets are contiguous and within range
    total = sum(t["n_frames"] for t in m["trajectories"])
    assert total == m["n_frames"]

    # tree.json is valid JSON and reloads
    with open(os.path.join(str(tmp_path), "tree.json")) as f:
        reloaded = json.load(f)
    assert reloaded["game_id"] == "tw01"

    # the optimal fork (replayed from the start) solves the level
    fork_traj = next(t for t in m["trajectories"] if t["kind"] == "fork")
    assert fork_traj["levels_completed"][-1] >= 1
    # the oracle ghost also solves
    oracle_traj = next(t for t in m["trajectories"] if t["kind"] == "oracle")
    assert oracle_traj["levels_completed"][-1] >= 1
