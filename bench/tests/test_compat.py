"""Verify the dual-emit JSON output preserves all legacy keys.

This test does NOT depend on the agent or LLM — it builds a synthetic
`BenchmarkReport` mirroring what AgentCoreRunner would produce, runs it
through `evaluate.save_results`, and asserts every key existing pre-refactor
analysis scripts expect is present at its original path.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

from bench.types import (
    AgentInfo,
    BenchmarkReport,
    BenchmarkSummary,
    GameReportEntry,
    WitnessScore,
)


# Import save_results from arc-witness-agent/evaluate.py
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AGENT = os.path.abspath(os.path.join(_HERE, "..", "arc-witness-agent"))
if _AGENT not in sys.path:
    sys.path.insert(0, _AGENT)


def _build_synthetic_report() -> BenchmarkReport:
    """Build a BenchmarkReport that mimics what AgentCoreRunner would produce."""
    legacy_metrics_tw01 = {
        "game_id": "tw01",
        "seed": 0,
        "total_levels": 10,
        "levels_completed": 1,
        "total_actions": 5000,
        "total_llm_calls": 14,
        "total_input_tokens": 1000,
        "total_output_tokens": 500,
        "estimated_cost_usd": 1.85,
        "unique_states": 1217,
        "rules_discovered": 3,
        "level_metrics": [
            {"level_index": 0, "completed": True, "actions_taken": 50, "baseline_actions": 11},
            {"level_index": 1, "completed": False, "actions_taken": 4950, "baseline_actions": 15},
        ],
        "overall_efficiency": 0.22,
    }

    return BenchmarkReport(
        agent=AgentInfo(name="arc-agent-v2", extras={"model": "anthropic/claude-opus-4.7"}),
        seed=0,
        games=[
            GameReportEntry(
                game_id="tw01",
                score=WitnessScore(
                    game_id="tw01",
                    score=4.18,
                    levels_completed=1,
                    levels_total=16,
                    actions=5000,
                    level_scores=[100.0, 0.0] + [0.0] * 14,
                    level_actions=[50, 4950] + [0] * 14,
                    level_baseline_actions=[11, 15, 15, 17, 18, 18, 20, 20, 28, 30, 11, 14, 18, 20, 20, 20],
                ),
                elapsed_s=151.5,
                error=None,
                legacy={"agent_extras": {
                    "estimated_cost_usd": 1.85,
                    "unique_states": 1217,
                    "overall_efficiency": 0.22,
                    "legacy_metrics": legacy_metrics_tw01,
                }},
            )
        ],
        summary=BenchmarkSummary(
            total_games=1,
            successful_games=1,
            total_levels_completed=1,
            total_levels=16,
            total_actions=5000,
            total_elapsed_s=151.5,
            overall_score=4.18,
            first_n_completed={1: 1, 3: 0, 5: 0, 10: 0, 20: 0, 50: 0},
        ),
    )


def test_save_results_preserves_all_legacy_top_level_keys() -> None:
    from evaluate import save_results  # type: ignore[import-not-found]

    report = _build_synthetic_report()
    config = {
        "llm": {
            "model": "anthropic/claude-opus-4.7",
            "fallback_model": "anthropic/claude-sonnet-4",
            "provider": "openrouter",
            "max_tokens": 16000,
            "temperature": 0.7,
            "thinking_budget": 0,
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        out_path = tmp.name
    try:
        save_results(report, out_path, config=config)
        with open(out_path) as f:
            data = json.load(f)
    finally:
        os.unlink(out_path)

    # ── Legacy top-level keys (existing analysis scripts read these) ──
    for k in [
        "summary",
        "games",
        "timestamp",
        "mode",
        "model",
        "fallback_model",
        "provider",
        "max_tokens",
        "temperature",
        "thinking_budget",
    ]:
        assert k in data, f"missing legacy top-level key: {k!r}"

    # ── Legacy summary fields (under "summary") ──
    s = data["summary"]
    for k in [
        "total_games",
        "successful_games",
        "total_levels_completed",
        "total_levels",
        "total_actions",
        "total_unique_states",
        "total_cost_usd",
        "total_elapsed_s",
        "overall_efficiency",
    ]:
        assert k in s, f"missing legacy summary key: {k!r}"

    # Legacy summary uses pre-refactor "buggy" denominator: sum of
    # len(level_metrics) per game = 2 (tw01 had 2 level_metrics entries)
    assert s["total_levels"] == 2, (
        f"legacy total_levels should be sum of level_metrics len, got {s['total_levels']}"
    )
    assert s["total_levels_completed"] == 1
    assert s["total_unique_states"] == 1217
    assert s["total_cost_usd"] == 1.85

    # ── Per-game legacy "metrics" preserved ──
    g0 = data["games"][0]
    assert g0["game_id"] == "tw01"
    assert "metrics" in g0, "legacy 'metrics' field missing"
    assert g0["metrics"]["levels_completed"] == 1
    assert g0["metrics"]["estimated_cost_usd"] == 1.85
    assert "level_metrics" in g0["metrics"]
    assert "elapsed_s" in g0

    # ── New bench fields also present ──
    assert data["schema_version"] == "2.0"
    assert "agent" in data
    assert "summary_official" in data, "new aggregate summary should be preserved"
    s_off = data["summary_official"]
    assert s_off["total_levels"] == 16, "official total_levels should be levels_total"
    assert s_off["overall_score"] == 4.18
    assert "first_n_completed" in s_off
    # Per-game: new "score" subkey
    assert "score" in g0
    assert g0["score"]["levels_completed"] == 1
    assert g0["score"]["levels_total"] == 16
    assert g0["score"]["score"] == 4.18

    # ── LLM config metadata correctly forwarded ──
    assert data["model"] == "anthropic/claude-opus-4.7"
    assert data["temperature"] == 0.7
    assert data["thinking_budget"] == 0


def test_save_results_handles_no_config() -> None:
    from evaluate import save_results  # type: ignore[import-not-found]

    report = _build_synthetic_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        out_path = tmp.name
    try:
        save_results(report, out_path, config=None)
        with open(out_path) as f:
            data = json.load(f)
    finally:
        os.unlink(out_path)

    # No config → no model/temperature fields, but everything else still works.
    assert "summary" in data
    assert "games" in data
    assert "timestamp" in data
    assert "mode" in data
    assert "model" not in data
