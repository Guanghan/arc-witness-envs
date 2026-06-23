"""P0 acceptance gates — GATE-A (determinism + restore), GATE-B (picklability),
GATE-L9 (fork flag never rides through a snapshot), fork isolation, branch.

Run: python -m pytest oversight/tests/test_snapshot_determinism.py
"""
import os
import pickle
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from oversight import branch, fork, is_forked, restore, snapshot  # noqa: E402
from oversight.resolve import resolve_root_game  # noqa: E402
from oversight.tests.conftest import ALL_GAMES, ai, digest, first_solution, load_game  # noqa: E402


def _corrupt(root):
    """Mutate game-specific + base fields so a no-op restore would be caught."""
    for attr in ("_path", "_blue_path", "_yellow_path"):
        v = getattr(root, attr, None)
        if isinstance(v, list):
            v.append((99, 99))
    for attr in ("_squares", "_stars", "_triangles", "_erasers", "_tetris", "_filters"):
        v = getattr(root, attr, None)
        if isinstance(v, dict):
            v[(99, 99)] = 7
        elif isinstance(v, set):
            v.add((99, 99))
    root._score = 5  # in-range sentinel (engine validates levels_completed <= 254)
    root._action_count = 77


@pytest.mark.parametrize("gid", ALL_GAMES)
def test_determinism_and_restore(gid):
    """GATE-A: two fresh runs match; corrupt+restore reproduces the fresh run;
    a post-restore agent RESET replays deterministically."""
    actions = first_solution(gid)

    # (1) two fresh games, same actions -> identical
    d_fresh = digest(load_game(gid, seed=0), actions)
    assert digest(load_game(gid, seed=0), actions) == d_fresh, f"{gid}: fresh runs diverged"

    # (2) snapshot fresh, advance + corrupt, restore, replay == fresh.
    # Advance first (legit mutation), THEN corrupt fields directly, THEN
    # restore (no perform_action on corrupted state, which the engine would
    # reject), so the digest match proves restore fully overwrote __dict__.
    g = load_game(gid, seed=0)
    snap = snapshot(g)
    for n in actions[: max(1, len(actions) // 2)]:
        g.perform_action(ai(n))
    _corrupt(resolve_root_game(g))
    restore(g, snap)
    # restore must have undone the corruption (check BEFORE replay, which mutates)
    assert resolve_root_game(g)._score == snap.score
    assert digest(g, actions) == d_fresh, f"{gid}: restore did not reproduce fresh trajectory"

    # (3) post-restore RESET replays deterministically vs a fresh+RESET game
    restore(g, snap)
    g.perform_action(ai(0))  # RESET
    d_reset = digest(g, actions)
    g3 = load_game(gid, seed=0)
    g3.perform_action(ai(0))
    assert digest(g3, actions) == d_reset, f"{gid}: post-restore RESET diverged"


@pytest.mark.parametrize("gid", ALL_GAMES)
def test_snapshot_isolation(gid):
    """GATE-B (deepcopy-backed): a snapshot is an isolated capture and a fork is
    an independent copy; mutating one never perturbs the other."""
    g = load_game(gid, seed=0)
    snap = snapshot(g)
    assert snap.frame_hash and len(snap.sid) == 64
    assert isinstance(snap.payload, dict) and "_state" in snap.payload

    child = fork(g)
    assert is_forked(child) and not is_forked(g)

    # mutate the child heavily; the parent and the snapshot stay intact
    actions = first_solution(gid)
    digest(child, actions)
    # restoring the parent from its own snapshot still reproduces a fresh run
    restore(g, snap)
    assert digest(g, actions) == digest(load_game(gid, seed=0), actions)


def test_raw_pickle_roundtrip_is_unsupported():
    """Documents WHY snapshots are deepcopy-backed, not pickle blobs: arcengine's
    GameAction enum does not round-trip through pickle. If this ever starts
    passing, pickle-to-disk persistence for the moment library can be enabled.
    """
    g = load_game("tw01", seed=0)
    try:
        pickle.loads(pickle.dumps(g.__dict__))
    except Exception:
        return  # expected today (GameAction(0) is invalid)
    pytest.skip("arcengine GameAction now pickles — revisit moment-library disk persistence")


def test_fork_flag_not_in_snapshot():
    """GATE-L9: forked-ness lives off __dict__, so it never rides through a
    snapshot blob onto a live (scored) game."""
    src = load_game("tw07", seed=0)
    child = fork(src)
    assert is_forked(child)
    snap = snapshot(child)
    live = load_game("tw07", seed=0)
    restore(live, snap)
    assert not is_forked(live), "forked flag leaked through snapshot/restore"


def test_fork_isolation():
    """A mutated fork does not perturb its parent."""
    g = load_game("tw01", seed=0)
    actions = first_solution("tw01")
    child = fork(g)
    digest(child, actions)  # mutate the child
    # parent, untouched, still matches a brand-new game
    assert digest(g, actions) == digest(load_game("tw01", seed=0), actions)


def test_branch_does_not_mutate_live():
    """branch() runs on a fork; the live game is byte-unchanged."""
    g = load_game("tw03", seed=0)
    actions = first_solution("tw03")
    before = snapshot(g).frame_hash
    res = branch(g, actions)
    after = snapshot(g).frame_hash
    assert before == after, "branch mutated the live game"
    assert len(res.frames) == len(actions)


def test_branch_from_snapshot_replays():
    """branch(from_snapshot=...) reproduces the snapshot's continuation."""
    gid = "tw01"
    actions = first_solution(gid)
    g = load_game(gid, seed=0)
    snap = snapshot(g)
    res = branch(g, actions, from_snapshot=snap)
    # a plain fresh replay (raw frames) should yield the same outcome sequence
    ref = branch(load_game(gid, seed=0), actions)
    assert res.levels_completed == ref.levels_completed
    assert res.states == ref.states
