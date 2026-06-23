"""P2 acceptance gates — GATE-G (solution status + replay-to-solved),
GATE-H (baseline matches metadata), coverage, GATE-V (state_value), rule cards,
and solve_now.

Run: python -m pytest oversight/tests/test_oracle.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from oversight import SolutionStatus, WitnessOracle, snapshot  # noqa: E402
from oversight.resolve import resolve_root_game  # noqa: E402
from oversight.tests.conftest import ALL_GAMES, ai, load_game  # noqa: E402

ORACLE = WitnessOracle()


def _first_with_solution(game_id):
    """(level_index, actions, validated) for the first level that has a solution."""
    for i, e in enumerate(ORACLE._levels(game_id)):
        if e.get("solution_actions"):
            return i, list(e["solution_actions"]), bool(e.get("validated"))
    return None


@pytest.mark.parametrize("gid", ALL_GAMES)
def test_solution_status_and_replay(gid):
    """GATE-G: the stored solution replays to a solved level, with the right
    typed status (VALIDATED_OPTIMAL, or HANDCRAFTED_EXAMPLE for tw09/tw10)."""
    found = _first_with_solution(gid)
    assert found is not None, f"{gid}: no stored solution at all"
    level, actions, validated = found

    acts, status = ORACLE.solution(gid, level)
    assert acts == actions
    if validated:
        assert status is SolutionStatus.VALIDATED_OPTIMAL
    else:
        assert status is SolutionStatus.HANDCRAFTED_EXAMPLE  # tw09 / tw10
    assert actions[-1] == 5, f"{gid}: solution should end in CONFIRM"

    # replay it from that level and confirm it solves
    g = load_game(gid, seed=0)
    resolve_root_game(g).set_level(level)
    fd = None
    for n in actions:
        fd = g.perform_action(ai(n))
    assert fd is not None and fd.levels_completed >= 1, f"{gid}: stored solution did not solve level {level}"


def test_unknown_status_for_configonly_level():
    """A level with no stored solution reports UNKNOWN."""
    # tw12 has only 4 solved of 160 — find a config-only level
    for i, e in enumerate(ORACLE._levels("tw12")):
        if not e.get("solution_actions"):
            acts, status = ORACLE.solution("tw12", i)
            assert acts is None and status is SolutionStatus.UNKNOWN
            return
    pytest.skip("no config-only level found in tw12")


@pytest.mark.parametrize("gid", ALL_GAMES)
def test_baseline_matches_metadata(gid):
    """GATE-H: baseline(source='bench') equals metadata.json baseline_actions."""
    meta_ba = ORACLE._meta(gid).get("baseline_actions", [])
    n = min(len(meta_ba), len(ORACLE._levels(gid)))
    assert n > 0
    for level in range(0, n, max(1, n // 5)):  # sample
        assert ORACLE.baseline(gid, level, source="bench") == int(meta_ba[level])


def test_coverage_matches_known_truth():
    cov = ORACLE.coverage()
    assert cov["tw12"]["validated"] == 4
    assert cov["tw09"]["validated"] == 0 and cov["tw09"]["handcrafted"] == 5
    assert cov["tw10"]["validated"] == 0 and cov["tw10"]["handcrafted"] == 5
    assert cov["tw07"]["validated"] == 359
    total = sum(c["validated"] for c in cov.values())
    assert total == 949


@pytest.mark.parametrize("gid", ALL_GAMES)
def test_rule_card_present(gid):
    card = ORACLE.rule_card(gid)
    assert card and gid in card.lower()


def test_state_value_structure_and_honesty():
    """GATE-V: state_value returns well-formed estimates; on a hard region game
    a 0-win result is reported as informative=False, not a misleading 0."""
    # tw07 level 0 from the start: random rollouts ~never win region constraints
    g = load_game("tw07", seed=0)
    snap = snapshot(g)
    est = ORACLE.state_value(snap, rollouts=16, seed=0)
    assert est.rollouts == 16
    assert 0.0 <= est.success_rate <= 1.0
    assert est.success_rate == est.n_wins / est.rollouts
    assert est.informative == (est.n_wins > 0)
    assert est.reachable == (est.n_wins > 0)
    assert est.optimal_moves is not None

    # state_value must not mutate the live game
    assert snapshot(g).frame_hash == snap.frame_hash


def test_batch_resolve_dryrun_reproduces():
    """Re-solving validated levels reproduces solutions (mechanism check, dry-run)."""
    rep = ORACLE.batch_resolve("tw01", levels=[0, 1], only_unsolved=False, timeout=10.0)
    assert rep["game_id"] == "tw01" and rep["attempted"] == 2
    statuses = {r["level"]: r["status"] for r in rep["results"]}
    assert statuses[0] == "solved" and statuses[1] == "solved"
    assert rep["solved"] == 2


def test_batch_resolve_skips_already_solved():
    """only_unsolved=True marks validated levels 'already' without re-solving."""
    rep = ORACLE.batch_resolve("tw01", levels=[0], only_unsolved=True)
    assert rep["attempted"] == 0
    assert rep["results"][0]["status"] == "already"


def test_batch_resolve_persist(tmp_path):
    """persist=True writes solutions back to a (temp-copied) levels JSON."""
    import json
    import os
    import shutil

    os.makedirs(tmp_path / "levels")
    os.makedirs(tmp_path / "environment_files" / "tw01")
    shutil.copy(os.path.join(ORACLE._root, "levels", "tw01_levels.json"),
                tmp_path / "levels" / "tw01_levels.json")
    shutil.copy(os.path.join(ORACLE._root, "environment_files", "tw01", "metadata.json"),
                tmp_path / "environment_files" / "tw01" / "metadata.json")

    orc = WitnessOracle(repo_root=str(tmp_path))
    rep = orc.batch_resolve("tw01", levels=[0], only_unsolved=False, timeout=10.0, persist=True)
    assert rep["solved"] == 1

    with open(tmp_path / "levels" / "tw01_levels.json") as f:
        doc = json.load(f)
    assert doc["levels"][0]["solution_actions"], "persisted solution missing"
    assert doc["levels"][0]["validated"] is True
    assert doc["levels"][0]["solution_actions"][-1] == 5  # CONFIRM-terminated


def test_solve_now_roundtrip():
    """solve_now re-derives a CONFIRM-terminated winning sequence for a solver
    game, and returns None for a no-solver game (tw09/tw10)."""
    # a small validated tw01 level
    level, _, _ = _first_with_solution("tw01")
    acts = ORACLE.solve_now("tw01", level, timeout=10.0)
    assert acts and acts[-1] == 5
    g = load_game("tw01", seed=0)
    resolve_root_game(g).set_level(level)
    fd = None
    for n in acts:
        fd = g.perform_action(ai(n))
    assert fd.levels_completed >= 1

    # tw09 has no solver -> None
    assert ORACLE.solve_now("tw09", 0, timeout=2.0) is None
