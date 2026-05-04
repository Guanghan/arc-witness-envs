"""Verify all 13 witness games' metadata loads and structure is consistent."""

from __future__ import annotations

import pytest

from bench.catalog import GAME_CLASSES, list_games, load_game_info


# Real total level counts per the levels/<g>_levels.json files
# (these are also documented in docs/witness-results.md).
EXPECTED_REAL_TOTALS = {
    "tw01": 16, "tw02": 62, "tw03": 248, "tw04": 26, "tw05": 55,
    "tw06": 144, "tw07": 502, "tw08": 108, "tw09": 5, "tw10": 5,
    "tw11": 410, "tw12": 160, "tw13": 131,
}


def test_list_games_returns_all_thirteen() -> None:
    games = list_games()
    assert games == [f"tw{i:02d}" for i in range(1, 14)]
    assert len(games) == 13


def test_game_classes_match_list_games() -> None:
    assert sorted(GAME_CLASSES.keys()) == list_games()


@pytest.mark.parametrize("game_id", list_games())
def test_load_game_info_succeeds_for_all_games(game_id: str) -> None:
    info = load_game_info(game_id)
    assert info.game_id == game_id
    assert info.baseline_actions, f"{game_id} has empty baseline_actions"
    assert all(b > 0 for b in info.baseline_actions), (
        f"{game_id} has non-positive baseline_actions: {info.baseline_actions}"
    )
    assert info.scoreable_levels == len(info.baseline_actions)
    # Real total should match what we know
    assert info.real_total_levels == EXPECTED_REAL_TOTALS[game_id], (
        f"{game_id} real_total_levels mismatch: got {info.real_total_levels}, "
        f"expected {EXPECTED_REAL_TOTALS[game_id]}"
    )


def test_load_game_info_unknown_game_raises() -> None:
    with pytest.raises(ValueError, match="Unknown witness game"):
        load_game_info("tw99")


def test_total_baseline_levels_summary() -> None:
    """Quick sanity check: sum of scoreable_levels across all games."""
    total = sum(load_game_info(g).scoreable_levels for g in list_games())
    # Whatever the exact number, ensure it's substantial — agent's
    # historical denominator was 146 (buggy); real is > 100 in baseline_actions.
    assert total >= 100, f"unexpectedly low total scoreable levels: {total}"
