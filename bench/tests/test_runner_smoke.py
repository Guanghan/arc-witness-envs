"""End-to-end runner test with a stub agent — no LLM, no real game env.

Validates the plumbing from `agent.run_on_game()` → score → `BenchmarkReport`
without depending on the agent or LLM API.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pytest

from bench.protocols import AgentProtocol
from bench.runner import run_batch, run_batch_multi_seed, run_single_game
from bench.types import (
    AgentInfo,
    AgentRunResult,
    LevelOutcome,
    WitnessGameState,
)


class StubAgent:
    """Returns canned outcomes per game. No game interaction.

    Args:
        canned: dict {game_id: list of (level_index, completed, actions_taken)}.
    """

    def __init__(
        self,
        canned: Dict[str, List[tuple]],
        state: WitnessGameState = WitnessGameState.NOT_FINISHED,
    ) -> None:
        self.canned = canned
        self.state = state
        self.calls = 0

    def run_on_game(
        self,
        game: Any,
        game_id: str,
        seed: int = 0,
        verbose: bool = False,
        max_levels: Optional[int] = None,
    ) -> AgentRunResult:
        self.calls += 1
        outcomes = self.canned.get(game_id, [])
        levels = [
            LevelOutcome(level_index=li, completed=c, actions_taken=a)
            for (li, c, a) in outcomes
        ]
        return AgentRunResult(
            game_id=game_id,
            seed=seed,
            levels=levels,
            total_actions=sum(a for _, _, a in outcomes),
            resets=0,
            state=self.state,
            extra={"stub": True},
        )


def test_stubagent_satisfies_agent_protocol() -> None:
    agent = StubAgent({})
    assert isinstance(agent, AgentProtocol)


def test_run_single_game_with_stub_agent() -> None:
    # tw09 has 5 baselines: [b0, b1, b2, b3, b4]
    # Stub solves first 2 levels with optimal actions.
    canned = {
        "tw09": [
            (0, True, 0),  # actions=0 → use baseline-as-actions trick? Just match baseline
            (1, True, 0),
        ]
    }
    # We don't know baselines without loading them. Use a stub that emits
    # actions equal to baselines (set later by the runner) → score=100.
    # Actually simpler: emit actions=1 per level, let scoring use real
    # baselines from metadata. We'll just check the structural fields.
    canned = {"tw09": [(0, True, 5), (1, True, 5)]}
    agent = StubAgent(canned, state=WitnessGameState.NOT_FINISHED)

    score, extras, elapsed, err = run_single_game(agent, "tw09")
    assert err is None
    assert score.game_id == "tw09"
    assert score.levels_completed == 2
    assert score.levels_total == 5  # tw09 has 5 baseline levels
    assert score.actions == 10  # sum of actions across all levels (incl. unsolved=0)
    assert extras == {"stub": True}
    assert elapsed > 0


def test_run_single_game_uses_canonical_baselines() -> None:
    """Agent emits LevelOutcome with baseline_actions=0; runner overrides
    from WitnessGameInfo.baseline_actions[level_index]."""
    # tw09 baseline_actions are real numbers from metadata; agent doesn't know them.
    canned = {"tw09": [(0, True, 1)]}
    agent = StubAgent(canned)

    score, _, _, err = run_single_game(agent, "tw09")
    assert err is None
    # level_baseline_actions[0] should now reflect tw09's metadata, not the
    # 0 the agent emitted.
    assert score.level_baseline_actions[0] > 0, (
        "runner should overwrite baseline_actions from WitnessGameInfo"
    )


def test_run_batch_aggregates_correctly() -> None:
    # 3 simple games. Hand-compute the aggregate.
    canned = {
        "tw09": [(0, True, 5), (1, True, 5)],   # 2/5
        "tw10": [(0, True, 5)],                  # 1/5
        "tw01": [],                               # 0/16
    }
    agent = StubAgent(canned)
    report = run_batch(
        agent,
        game_ids=["tw09", "tw10", "tw01"],
        agent_info=AgentInfo(name="stub-test"),
    )

    assert report.summary.total_games == 3
    assert report.summary.successful_games == 3  # no errors
    assert report.summary.total_levels_completed == 3  # 2 + 1 + 0
    # total_levels = sum(scoreable_levels) for tw09 + tw10 + tw01 = 5 + 5 + 16 = 26
    assert report.summary.total_levels == 26
    # first_n_completed: K=1 hits 2 games, K=3 hits 0
    assert report.summary.first_n_completed[1] == 2
    assert report.summary.first_n_completed[3] == 0
    # Per-game ordering preserved
    assert [e.game_id for e in report.games] == ["tw09", "tw10", "tw01"]
    # Agent identity preserved
    assert report.agent.name == "stub-test"


def test_run_batch_handles_agent_errors() -> None:
    class BrokenAgent:
        def run_on_game(self, *a, **kw):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    report = run_batch(BrokenAgent(), game_ids=["tw09"], agent_info=AgentInfo(name="b"))
    assert report.summary.total_games == 1
    assert report.summary.successful_games == 0
    assert report.games[0].error is not None
    assert "boom" in report.games[0].error
    # Score is zeroed but levels_total is still the canonical value
    assert report.games[0].score.levels_completed == 0
    assert report.games[0].score.levels_total == 5  # tw09 has 5 baselines


def test_run_batch_default_runs_all_games() -> None:
    """If game_ids=None, runs all 13."""
    agent = StubAgent({})
    report = run_batch(agent, agent_info=AgentInfo(name="stub"))
    assert report.summary.total_games == 13
    assert agent.calls == 13


def test_run_batch_calls_on_game_done_callback() -> None:
    seen: List[str] = []

    def cb(gid, score, elapsed, err):  # type: ignore[no-untyped-def]
        seen.append(gid)

    agent = StubAgent({})
    run_batch(
        agent,
        game_ids=["tw09", "tw10"],
        agent_info=AgentInfo(name="stub"),
        on_game_done=cb,
    )
    assert seen == ["tw09", "tw10"]


# ── Resets tracking ──────────────────────────────────────────────────────


class ResettingAgent:
    """Agent that performs N RESET actions (and nothing else) on each game."""

    def __init__(self, n_resets_per_game: int) -> None:
        self.n_resets = n_resets_per_game

    def run_on_game(
        self,
        game: Any,
        game_id: str,
        seed: int = 0,
        verbose: bool = False,
        max_levels: Optional[int] = None,
    ) -> AgentRunResult:
        from arcengine import ActionInput
        from arcengine.enums import GameAction

        for _ in range(self.n_resets):
            game.perform_action(ActionInput(id=GameAction.RESET))

        return AgentRunResult(
            game_id=game_id,
            seed=seed,
            levels=[],
            total_actions=self.n_resets,
            resets=999,  # agent's claim — should be overridden by runner
            state=WitnessGameState.NOT_FINISHED,
        )


def test_resets_counted_by_runner() -> None:
    """The benchmark counts RESETs at the perform_action boundary, NOT
    relying on the agent to self-report (which can be wrong or 0)."""
    from bench.runner import run_single_game

    agent = ResettingAgent(n_resets_per_game=3)
    score, _, _, err = run_single_game(agent, "tw09")
    assert err is None
    # Authoritative: 3 RESETs were observed at the perform_action boundary.
    assert score.resets == 3, (
        f"expected runner to count 3 resets, got {score.resets} "
        "(agent claimed 999 — runner should ignore that)"
    )


def test_resets_counted_per_game_independently() -> None:
    """Reset count is per-game, not cumulative across the batch."""
    from bench.runner import run_batch

    agent = ResettingAgent(n_resets_per_game=2)
    report = run_batch(
        agent, game_ids=["tw01", "tw02", "tw09"], agent_info=AgentInfo(name="reset-2x")
    )
    for entry in report.games:
        assert entry.score.resets == 2, (
            f"{entry.game_id}: expected 2 resets, got {entry.score.resets}"
        )


def test_resets_zero_when_agent_does_nothing() -> None:
    """Non-resetting StubAgent → resets remains 0 (or None coerced to 0)."""
    from bench.runner import run_single_game

    canned = {"tw09": [(0, True, 5)]}
    agent = StubAgent(canned)
    score, _, _, err = run_single_game(agent, "tw09")
    assert err is None
    # StubAgent emits no actions → resets stays at 0.
    assert (score.resets or 0) == 0


# ── Multi-run / multi-seed ───────────────────────────────────────────────


class SeedSensitiveAgent:
    """Agent whose performance depends on seed — for testing MAX-aggregation."""

    def __init__(self, score_by_seed: Dict[int, int]) -> None:
        # score_by_seed[seed] = number of actions to use solving level 0
        # (lower = better score, since (baseline/actions)^2 * 100)
        self.score_by_seed = score_by_seed
        self.calls = 0

    def run_on_game(
        self,
        game: Any,
        game_id: str,
        seed: int = 0,
        verbose: bool = False,
        max_levels: Optional[int] = None,
    ) -> AgentRunResult:
        self.calls += 1
        actions = self.score_by_seed.get(seed, 100)
        if actions == 0:
            # Treat as failure
            return AgentRunResult(
                game_id=game_id, seed=seed, levels=[],
                state=WitnessGameState.NOT_FINISHED,
            )
        return AgentRunResult(
            game_id=game_id,
            seed=seed,
            levels=[LevelOutcome(level_index=0, completed=True, actions_taken=actions)],
            total_actions=actions,
            state=WitnessGameState.NOT_FINISHED,
        )


def test_multi_seed_takes_max_score_per_game() -> None:
    """Per-game score = MAX over runs, matching arc_agi.scorecard
    EnvironmentScoreList.score = max(...)."""
    from bench.runner import run_batch_multi_seed

    # seed=0 → 50 actions; seed=1 → 10 actions (best, matches baseline 11 closely)
    # seed=2 → 0 actions (failure)
    agent = SeedSensitiveAgent({0: 50, 1: 10, 2: 0})
    report = run_batch_multi_seed(
        agent,
        game_ids=["tw01"],
        seeds=[0, 1, 2],
        agent_info=AgentInfo(name="seed-sensitive"),
    )
    assert agent.calls == 3  # one call per seed

    entry = report.games[0]
    per_run_scores = [r["score"] for r in entry.legacy["per_run_scores"]]
    assert len(per_run_scores) == 3
    # Aggregated score must equal the MAX of per-run scores
    assert math.isclose(entry.score.score, max(per_run_scores))
    # Best run was seed=1 (index 1)
    assert entry.legacy["best_run_idx"] == 1
    assert entry.legacy["per_run_seeds"] == [0, 1, 2]


def test_multi_seed_run_metadata_records_seeds_and_n_runs() -> None:
    from bench.runner import run_batch_multi_seed

    agent = SeedSensitiveAgent({7: 10, 42: 20})
    report = run_batch_multi_seed(
        agent, game_ids=["tw09"], seeds=[7, 42],
        agent_info=AgentInfo(name="m"),
    )
    assert report.run_metadata["seeds"] == [7, 42]
    assert report.run_metadata["n_runs"] == 2


def test_multi_seed_single_seed_shortcut_matches_run_batch() -> None:
    """seeds=[0] should produce same shape as run_batch(seed=0)."""
    from bench.runner import run_batch, run_batch_multi_seed

    canned = {"tw01": [(0, True, 10)]}
    agent_a = StubAgent(canned)
    agent_b = StubAgent(canned)

    rep_single = run_batch(
        agent_a, game_ids=["tw01"], seed=0, agent_info=AgentInfo(name="s")
    )
    rep_multi1 = run_batch_multi_seed(
        agent_b, game_ids=["tw01"], seeds=[0], agent_info=AgentInfo(name="s")
    )

    # Same per-game score
    assert math.isclose(rep_single.games[0].score.score, rep_multi1.games[0].score.score)
    assert rep_single.games[0].score.levels_completed == rep_multi1.games[0].score.levels_completed
    # Multi-run shortcut still records seed metadata
    assert rep_multi1.run_metadata["n_runs"] == 1
    assert rep_multi1.run_metadata["seeds"] == [0]


def test_multi_seed_empty_seeds_raises() -> None:
    from bench.runner import run_batch_multi_seed

    with pytest.raises(ValueError, match="seeds must be non-empty"):
        run_batch_multi_seed(StubAgent({}), game_ids=["tw01"], seeds=[])


def test_multi_seed_per_run_details_preserved() -> None:
    """Per-run scores, elapsed, errors all preserved in legacy."""
    from bench.runner import run_batch_multi_seed

    agent = SeedSensitiveAgent({0: 20, 1: 10, 2: 30})
    report = run_batch_multi_seed(
        agent, game_ids=["tw01"], seeds=[0, 1, 2],
        agent_info=AgentInfo(name="m"),
    )
    legacy = report.games[0].legacy
    assert "per_run_scores" in legacy
    assert "per_run_elapsed" in legacy
    assert "per_run_errors" in legacy
    assert "per_run_seeds" in legacy
    assert "best_run_idx" in legacy
    assert len(legacy["per_run_scores"]) == 3
    assert len(legacy["per_run_elapsed"]) == 3
    # All runs succeeded → no errors
    assert all(e is None for e in legacy["per_run_errors"])


def test_multi_seed_overall_score_is_mean_of_aggregated() -> None:
    """summary.overall_score = mean of per-game MAX-aggregated scores."""
    from bench.runner import run_batch_multi_seed

    agent = SeedSensitiveAgent({0: 10, 1: 20})
    report = run_batch_multi_seed(
        agent, game_ids=["tw01", "tw09"], seeds=[0, 1],
        agent_info=AgentInfo(name="m"),
    )
    per_game_aggs = [e.score.score for e in report.games]
    expected = sum(per_game_aggs) / len(per_game_aggs)
    assert math.isclose(report.summary.overall_score, expected)
