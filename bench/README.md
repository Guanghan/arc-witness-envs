# `bench/` — Witness Benchmark Evaluation

Canonical evaluation infrastructure for the witness benchmark (tw01–tw13).
Mirrors the official ARC-AGI-3 SDK scoring methodology
(`arc_agi.scorecard`) so any agent implementing `AgentProtocol` can be
evaluated identically.

## Why this lives here

Best practice (as in the ARC-AGI-3 SDK, HumanEval, SWE-bench, AgentBench,
etc.) is for the **benchmark** to own the evaluation logic, with **agents
as pluggable consumers**. This makes:

- Multi-agent comparison apples-to-apples (same scoring formula for every
  agent).
- Scoring updates a single-source change (you don't have N agent repos to
  keep in sync).
- The benchmark publishable / open-sourceable on its own.

## Module layout

```
bench/
├── __init__.py           # Public exports
├── types.py              # Pydantic models (WitnessGameInfo, WitnessScore, …)
├── scoring.py            # WitnessScoreCalculator + helpers
├── catalog.py            # GAME_CLASSES, list_games, load_game, load_game_info
├── protocols.py          # AgentProtocol (typing.Protocol)
├── runner.py             # run_single_game, run_batch
├── cli.py                # python -m bench
├── __main__.py           # Entry point
└── tests/
    ├── test_scoring.py     # Bit-parity with arc_agi reference + corner cases
    ├── test_catalog.py     # All 13 games' metadata loadable
    ├── test_runner_smoke.py # Stub-agent end-to-end
    └── test_compat.py      # Dual-emit JSON keeps legacy keys
```

## Scoring formula

Per-level (capped at 115):

```
if completed and actions_taken > 0:
    score = ((baseline_actions / actions_taken) ** 2) * 100
else:
    score = 0.0
```

Per-game (1-based level_index weighted average):

```
weight        = level_index               (1, 2, 3, ...)
total_score   = sum(score[i] * weight[i])
total_weights = sum(weight[i])
max_weights   = sum(weight[i] for i where score[i] > 0)
final         = total_score / total_weights
final         = min(final, max_weights / total_weights * 100)
```

Multi-run aggregation (`aggregate_runs`):
- `score = max over runs`
- `levels_completed = max over runs`
- `resets = sum over runs`

This is bit-equivalent to `arc_agi.scorecard.EnvironmentScoreCalculator` —
verified by `test_scoring.py::test_parity_with_arc_agi_calculator`
(100 random sequences, score equality to 1e-9).

### Properties of the metric

- **Efficiency matters quadratically.** 2× the optimal action count gets
  25% credit. 5× gets 4%. "I solved it eventually" is not enough.
- **Deeper levels weigh more** (linearly in 1-based index). Solving 5
  late-game levels beats grinding 5 trivial intro levels.
- **Resets are free in scoring** but inflate `actions`, which hurts the
  efficiency score. Use them strategically.
- **Multi-run takes the best.** No penalty for failed exploration runs.

## Agent protocol

```python
@runtime_checkable
class AgentProtocol(Protocol):
    def run_on_game(
        self,
        game: Any,
        game_id: str,
        seed: int = 0,
        verbose: bool = False,
        max_levels: Optional[int] = None,
    ) -> AgentRunResult: ...
```

`game` is whatever `bench.catalog.load_game(game_id, seed)` returns — a
witness game instance with `.perform_action(ActionInput) -> FrameDataRaw`.

`AgentRunResult.levels` is a list of `LevelOutcome(level_index, completed,
actions_taken, ...)` (0-based). The runner overrides `baseline_actions`
from `WitnessGameInfo.baseline_actions[i]` before scoring, so agents
**never** need to know the benchmark's baselines.

See `arc-witness-agent/agent/adapters/eval_adapter.py` for a reference
adapter that wraps the existing `AgentCore` to satisfy this protocol.

## CLI usage

### List all benchmark games

```bash
cd arc-witness-envs
python -m bench --list-games
```

### Run a custom agent against the benchmark

```bash
PYTHONPATH=arc-witness-envs python -m bench \
    --agent some.module:AgentClass \
    --agent-args '{"config": {...}}' \
    --games tw01 tw02 \
    --max-levels 2 \
    -o eval_results/myagent.json
```

For ARC-Agent v2 specifically, prefer `arc-witness-agent/evaluate.py` —
it loads the YAML config and constructs `AgentCoreRunner` for you.

## Programmatic usage

```python
from bench import run_batch, AgentInfo
from my_agent_module import MyAgent  # implements AgentProtocol

agent = MyAgent(...)
report = run_batch(
    agent=agent,
    game_ids=["tw01", "tw02", "tw03"],
    seed=0,
    agent_info=AgentInfo(name="my-agent-v1"),
)

print(f"Overall score: {report.summary.overall_score:.2f}")
print(f"Levels solved: {report.summary.total_levels_completed}/{report.summary.total_levels}")

# Save the standard JSON report
with open("eval_results/myagent.json", "w") as f:
    f.write(report.model_dump_json(indent=2, exclude_none=True))
```

## Output JSON shape

`BenchmarkReport.model_dump_json` produces (top-level keys):

```
{
  "schema_version": "2.0",
  "generated_at": "2026-05-04T...",
  "agent": {"name": "...", "extras": {...}},
  "seed": 0,
  "games": [
    {"game_id": "tw01", "score": <WitnessScore>, "elapsed_s": ..., "error": null}
  ],
  "summary": {
    "total_games": 13,
    "successful_games": 13,
    "total_levels_completed": 44,
    "total_levels": 1872,                 // sum of scoreable_levels
    "total_actions": 65000,
    "total_elapsed_s": 3002.3,
    "overall_score": 4.18,                // weighted, official-style
    "first_n_completed": {1: 10, 3: 7, ...}
  },
  "run_metadata": {...}
}
```

For backward compatibility with arc-witness-agent's existing analysis
scripts, `arc-witness-agent/evaluate.py` writes a **dual-shape** JSON:
new bench fields PLUS legacy keys (`summary.total_levels` reverts to the
pre-refactor denominator, per-game `metrics` field is preserved). See
`arc-witness-agent/docs/evaluation-custom-vs-official.md`.

## Running the tests

```bash
cd arc-witness-envs
PYTHONPATH=. pytest bench/tests/ -v
```

41 tests should pass. The `test_parity_with_arc_agi_calculator` test
requires `arc_agi` to be installed (it is in the agent venv).

## Implemented features

- ✅ **Resets tracking** (2026-05-04) — `_ResetCountingGame` in `runner.py`
  transparently counts `RESET` actions at the env boundary. Per-game counts
  in `WitnessScore.resets`; aggregate in `BenchmarkSummary.total_resets`.
  No agent-side changes needed.
- ✅ **Tag aggregation** (2026-05-04) — `compute_tag_scores()` in
  `scoring.py` produces per-tag mean-of-game-scores. Exposed as
  `BenchmarkSummary.tag_scores: Dict[str, TagScore]`. CLI: `--tag-breakdown`
  prints a sorted per-tag table.

## Open / deferred items

- **Multi-run support in CLI** (`--n-runs N`, max-aggregate via
  `aggregate_runs()`). Function is shipped + tested, just not yet wired
  to CLI. Defer until variance estimate is needed for a paper / leaderboard
  submission.
- **Per-level resets**. Currently per-game only. Add when agent-internal
  reset accounting is needed (e.g., to detect tw09/tw10-style reset loops
  per level).
- **`level_tags` / `private_tags`** aggregation. Fields present in
  `WitnessGameInfo` but not yet populated in metadata.json.
- **ARC-AGI-3 SDK games** (`ls20`, `ft09`, `vc33`) are out of scope for
  this CLI — see `arc-witness-agent/evaluate_arc_agi_agent.py`.
