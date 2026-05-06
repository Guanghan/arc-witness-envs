"""Verify WitnessScoreCalculator is bit-equivalent to arc_agi SDK reference.

If `arc_agi` is not installed, the SDK-parity tests are skipped (module-only
formula tests still run).
"""

from __future__ import annotations

import importlib.util
import math
import random

import pytest

from bench.scoring import (
    SCORE_CAP,
    WitnessScoreCalculator,
    aggregate_runs,
    compute_tag_scores,
    first_n_hit_counts,
    score_one_game,
)
from bench.types import (
    AgentRunResult,
    GameReportEntry,
    LevelOutcome,
    TagScore,
    WitnessGameInfo,
    WitnessGameState,
    WitnessScore,
)


HAS_ARC_AGI = importlib.util.find_spec("arc_agi") is not None


# ── Per-level formula ────────────────────────────────────────────────────


def test_completed_level_optimal_actions_scores_100() -> None:
    calc = WitnessScoreCalculator(game_id="t")
    calc.add_level(level_index=1, completed=True, actions_taken=10, baseline_actions=10)
    s = calc.to_score()
    assert math.isclose(s.score, 100.0)
    assert s.level_scores == [100.0]
    assert s.levels_completed == 1
    assert s.actions == 10


def test_completed_level_double_actions_scores_25() -> None:
    calc = WitnessScoreCalculator(game_id="t")
    calc.add_level(level_index=1, completed=True, actions_taken=20, baseline_actions=10)
    s = calc.to_score()
    # (10/20)^2 * 100 = 25
    assert math.isclose(s.level_scores[0], 25.0)


def test_completed_level_half_actions_caps_at_115() -> None:
    calc = WitnessScoreCalculator(game_id="t")
    calc.add_level(level_index=1, completed=True, actions_taken=5, baseline_actions=10)
    s = calc.to_score()
    # (10/5)^2 * 100 = 400 → cap 115
    assert math.isclose(s.level_scores[0], SCORE_CAP)


def test_failed_level_scores_zero() -> None:
    calc = WitnessScoreCalculator(game_id="t")
    calc.add_level(level_index=1, completed=False, actions_taken=99, baseline_actions=10)
    s = calc.to_score()
    assert s.level_scores == [0.0]
    assert s.levels_completed == 0
    assert s.actions == 99  # actions still counted


def test_completed_level_zero_actions_scores_zero() -> None:
    calc = WitnessScoreCalculator(game_id="t")
    calc.add_level(level_index=1, completed=True, actions_taken=0, baseline_actions=10)
    s = calc.to_score()
    # actions_taken == 0 → score 0 (avoid div by zero)
    assert s.level_scores == [0.0]
    assert s.levels_completed == 1  # still counted as completed


# ── Per-game weighted aggregation ────────────────────────────────────────


def test_weighted_aggregation_by_level_index() -> None:
    """Level 1 weight=1, level 2 weight=2: (100*1 + 50*2)/(1+2) = 66.67."""
    calc = WitnessScoreCalculator(game_id="t")
    calc.add_level(level_index=1, completed=True, actions_taken=10, baseline_actions=10)  # → 100
    # Level 2: (10/14.142)^2 * 100 ≈ 50
    calc.add_level(
        level_index=2,
        completed=True,
        actions_taken=int(10 * math.sqrt(2)),
        baseline_actions=10,
    )  # → ≈50
    s = calc.to_score()
    # Both levels solved → max_weights = total_weights, so cap = 100
    # Score ≈ (100*1 + 50.something*2) / 3
    assert 60.0 < s.score < 75.0


def test_unsolved_levels_cap_score_via_max_score() -> None:
    """If only 1 of 3 levels solved, score capped by max_weights/total_weights*100."""
    calc = WitnessScoreCalculator(game_id="t")
    # Solve level 1 perfectly (score=100, weight=1)
    calc.add_level(level_index=1, completed=True, actions_taken=10, baseline_actions=10)
    # Fail levels 2 and 3 (weights 2, 3)
    calc.add_level(level_index=2, completed=False, actions_taken=0, baseline_actions=10)
    calc.add_level(level_index=3, completed=False, actions_taken=0, baseline_actions=10)
    s = calc.to_score()
    # total_score = 100*1 + 0*2 + 0*3 = 100
    # total_weights = 1+2+3 = 6
    # raw_score = 100/6 ≈ 16.67
    # max_weights = 1 (only level 1 solved)
    # max_score = 1/6 * 100 = 16.67
    # min(raw, max) = 16.67
    assert math.isclose(s.score, 100 / 6, rel_tol=1e-9)


def test_empty_calculator_to_score() -> None:
    calc = WitnessScoreCalculator(game_id="t")
    s = calc.to_score()
    assert s.score == 0.0
    assert s.levels_completed == 0
    assert s.levels_total == 0


# ── score_one_game with WitnessGameInfo ──────────────────────────────────


def test_score_one_game_iterates_full_baseline_length() -> None:
    """Even if the agent only reports 2 levels, scoring iterates all 5
    declared baseline levels and zeroes the missing ones."""
    info = WitnessGameInfo(
        game_id="t",
        baseline_actions=[10, 10, 10, 10, 10],
        real_total_levels=5,
    )
    run = AgentRunResult(
        game_id="t",
        levels=[
            LevelOutcome(level_index=0, completed=True, actions_taken=10),
            LevelOutcome(level_index=1, completed=True, actions_taken=10),
        ],
        total_actions=20,
        state=WitnessGameState.NOT_FINISHED,
    )
    s = score_one_game(info, run)
    assert s.levels_total == 5  # full denominator
    assert s.levels_completed == 2
    # Per-level scores: [100, 100, 0, 0, 0] with weights [1, 2, 3, 4, 5]
    # raw = (100 + 200) / 15 = 20.0
    # max_weights = 1+2 = 3 → max_score = 3/15*100 = 20.0
    assert math.isclose(s.score, 20.0, rel_tol=1e-9)


def test_score_one_game_no_levels() -> None:
    info = WitnessGameInfo(game_id="t", baseline_actions=[10, 10, 10])
    run = AgentRunResult(game_id="t", levels=[], state=WitnessGameState.NOT_FINISHED)
    s = score_one_game(info, run)
    assert s.score == 0.0
    assert s.levels_completed == 0
    assert s.levels_total == 3


def test_score_one_game_state_win_marks_completed() -> None:
    info = WitnessGameInfo(game_id="t", baseline_actions=[10])
    run = AgentRunResult(
        game_id="t",
        levels=[LevelOutcome(level_index=0, completed=True, actions_taken=10)],
        state=WitnessGameState.WIN,
    )
    s = score_one_game(info, run)
    assert s.completed is True


def test_score_one_game_score_cap_truncates_long_game() -> None:
    """A 50-level game where the agent solves the first 3, scored with cap=10:
    only the first 10 levels enter both numerator and denominator. The 47
    unsolved levels beyond the cap don't dilute the score."""
    info = WitnessGameInfo(
        game_id="long",
        baseline_actions=[10] * 50,
        real_total_levels=50,
    )
    run = AgentRunResult(
        game_id="long",
        levels=[
            LevelOutcome(level_index=0, completed=True, actions_taken=10),
            LevelOutcome(level_index=1, completed=True, actions_taken=10),
            LevelOutcome(level_index=2, completed=True, actions_taken=10),
        ],
        total_actions=30,
        state=WitnessGameState.NOT_FINISHED,
    )
    # Without cap: weights 1..50 sum to 1275, max_score = 6/1275*100 ≈ 0.47
    s_uncapped = score_one_game(info, run)
    assert s_uncapped.levels_total == 50
    assert math.isclose(s_uncapped.score, 6.0 / 1275 * 100, rel_tol=1e-9)

    # With cap=10: weights 1..10 sum to 55, max_score = 6/55*100 ≈ 10.9
    s_capped = score_one_game(info, run, score_cap=10)
    assert s_capped.levels_total == 10
    assert s_capped.levels_completed == 3
    assert math.isclose(s_capped.score, 6.0 / 55 * 100, rel_tol=1e-9)


def test_score_one_game_score_cap_zero_or_none_disables() -> None:
    """score_cap=None and score_cap=0 are both no-ops (full game scored)."""
    info = WitnessGameInfo(game_id="t", baseline_actions=[10, 10, 10])
    run = AgentRunResult(
        game_id="t",
        levels=[LevelOutcome(level_index=0, completed=True, actions_taken=10)],
        state=WitnessGameState.NOT_FINISHED,
    )
    s_none = score_one_game(info, run, score_cap=None)
    s_zero = score_one_game(info, run, score_cap=0)
    s_default = score_one_game(info, run)
    assert s_none.levels_total == 3
    assert s_zero.levels_total == 3
    assert s_default.levels_total == 3
    assert math.isclose(s_none.score, s_default.score)


def test_score_one_game_score_cap_larger_than_game_is_noop() -> None:
    """If cap exceeds game length, no truncation happens."""
    info = WitnessGameInfo(game_id="t", baseline_actions=[10, 10])
    run = AgentRunResult(
        game_id="t",
        levels=[LevelOutcome(level_index=0, completed=True, actions_taken=10)],
        state=WitnessGameState.NOT_FINISHED,
    )
    s = score_one_game(info, run, score_cap=100)
    assert s.levels_total == 2  # not 100


# ── Helpers ──────────────────────────────────────────────────────────────


def test_first_n_hit_counts() -> None:
    scores = [
        WitnessScore(game_id="a", score=0, levels_completed=0, levels_total=10, actions=0),
        WitnessScore(game_id="b", score=0, levels_completed=2, levels_total=10, actions=0),
        WitnessScore(game_id="c", score=0, levels_completed=10, levels_total=10, actions=0),
    ]
    counts = first_n_hit_counts(scores, cutoffs=(1, 3, 10))
    assert counts == {1: 2, 3: 1, 10: 1}


def test_aggregate_runs_takes_max_score() -> None:
    runs = [
        WitnessScore(game_id="a", score=20, levels_completed=2, levels_total=10, actions=100, resets=1),
        WitnessScore(game_id="a", score=50, levels_completed=5, levels_total=10, actions=200, resets=2),
        WitnessScore(game_id="a", score=10, levels_completed=1, levels_total=10, actions=50, resets=0),
    ]
    agg = aggregate_runs(runs)
    assert agg.score == 50
    assert agg.levels_completed == 5
    assert agg.actions == 350
    assert agg.resets == 3


def test_aggregate_runs_empty_raises() -> None:
    with pytest.raises(ValueError):
        aggregate_runs([])


# ── Parity vs official arc_agi SDK ───────────────────────────────────────


# ── Tag aggregation ──────────────────────────────────────────────────────


def _entry(game_id: str, score: float, levels_completed: int, levels_total: int, actions: int = 0) -> GameReportEntry:
    return GameReportEntry(
        game_id=game_id,
        score=WitnessScore(
            game_id=game_id, score=score,
            levels_completed=levels_completed, levels_total=levels_total,
            actions=actions,
        ),
    )


def _info(game_id: str, baselines: int, tags: list) -> WitnessGameInfo:
    return WitnessGameInfo(
        game_id=game_id,
        baseline_actions=[10] * baselines,
        real_total_levels=baselines,
        tags=tags,
    )


def test_compute_tag_scores_groups_by_tag() -> None:
    """Each game's tags create one bucket entry per tag."""
    entries = [
        _entry("a", 50.0, 5, 10),
        _entry("b", 30.0, 3, 10),
        _entry("c", 10.0, 1, 10),
    ]
    infos = {
        "a": _info("a", 10, ["spatial", "easy"]),
        "b": _info("b", 10, ["spatial", "hard"]),
        "c": _info("c", 10, ["temporal"]),
    }
    tag_scores = compute_tag_scores(entries, infos)

    assert set(tag_scores.keys()) == {"spatial", "easy", "hard", "temporal"}
    assert tag_scores["spatial"].game_ids == ["a", "b"]
    assert tag_scores["temporal"].game_ids == ["c"]


def test_tag_score_mean_matches_arithmetic_mean() -> None:
    entries = [_entry("a", 60.0, 5, 10), _entry("b", 40.0, 5, 10)]
    infos = {"a": _info("a", 10, ["x"]), "b": _info("b", 10, ["x"])}
    ts = compute_tag_scores(entries, infos)["x"]
    assert math.isclose(ts.mean_score, 50.0)
    assert ts.total_games == 2
    assert ts.total_levels == 20  # 10 + 10
    assert ts.total_levels_completed == 10  # 5 + 5


def test_compute_tag_scores_skips_games_with_no_tags() -> None:
    entries = [_entry("a", 50.0, 5, 10), _entry("b", 30.0, 3, 10)]
    infos = {
        "a": _info("a", 10, ["spatial"]),
        "b": _info("b", 10, []),  # no tags
    }
    tag_scores = compute_tag_scores(entries, infos)
    assert "spatial" in tag_scores
    assert tag_scores["spatial"].game_ids == ["a"]
    # No empty-string tag, no tags from "b"
    assert all(t != "" for t in tag_scores)


def test_compute_tag_scores_empty_input() -> None:
    assert compute_tag_scores([], {}) == {}


def test_compute_tag_scores_real_witness_metadata() -> None:
    """Run against the actual witness metadata.json files."""
    from bench.catalog import list_games, load_game_info

    # Build trivial dummy entries (score=0) — we only test grouping.
    infos = {gid: load_game_info(gid) for gid in list_games()}
    entries = [
        _entry(gid, 0.0, 0, infos[gid].scoreable_levels)
        for gid in list_games()
    ]

    tag_scores = compute_tag_scores(entries, infos)

    # 'witness' tag should cover all 13 games.
    assert "witness" in tag_scores
    assert tag_scores["witness"].total_games == 13

    # Confirmed groups from `metadata.json` recon:
    assert "path-constraint" in tag_scores
    assert sorted(tag_scores["path-constraint"].game_ids) == ["tw01", "tw12"]

    assert "meta-reasoning" in tag_scores
    assert sorted(tag_scores["meta-reasoning"].game_ids) == ["tw07", "tw13"]

    # Singleton tags exist:
    assert tag_scores["tiling"].total_games == 1


@pytest.mark.skipif(not HAS_ARC_AGI, reason="arc_agi not installed in this env")
def test_parity_with_arc_agi_calculator() -> None:
    """100 random `add_level` sequences: our calculator must produce the
    same `score` and `level_scores` as `arc_agi.scorecard.EnvironmentScoreCalculator`.
    """
    from arc_agi.scorecard import EnvironmentScoreCalculator  # type: ignore

    rng = random.Random(0)
    n_trials = 100
    for trial in range(n_trials):
        n_levels = rng.randint(0, 20)
        ours = WitnessScoreCalculator(game_id="t")
        theirs = EnvironmentScoreCalculator()
        for level_idx in range(1, n_levels + 1):
            completed = rng.random() < 0.5
            actions = rng.randint(0, 200)
            baseline = rng.randint(1, 50)
            ours.add_level(
                level_index=level_idx,
                completed=completed,
                actions_taken=actions,
                baseline_actions=baseline,
            )
            theirs.add_level(
                level_index=level_idx,
                completed=completed,
                actions_taken=actions,
                baseline_actions=baseline,
            )

        our_score = ours.to_score()
        their_score = theirs.to_score()

        assert math.isclose(our_score.score, their_score.score, rel_tol=1e-9, abs_tol=1e-9), (
            f"trial {trial}: scores diverge: {our_score.score} vs {their_score.score}"
        )
        assert our_score.levels_completed == their_score.levels_completed
        assert list(our_score.level_scores or []) == list(their_score.level_scores or [])
        assert list(our_score.level_actions or []) == list(their_score.level_actions or [])
        assert list(our_score.level_baseline_actions or []) == list(
            their_score.level_baseline_actions or []
        )
        assert our_score.actions == their_score.actions
