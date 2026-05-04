"""End-to-end runner test with a stub agent — no LLM, no real game env.

Validates the plumbing from `agent.run_on_game()` → score → `BenchmarkReport`
without depending on the agent or LLM API.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pytest

from bench.protocols import AgentProtocol
from bench.runner import run_batch, run_single_game
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
