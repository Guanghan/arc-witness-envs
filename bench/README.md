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
- Scoring updates a single-source change.
- The benchmark publishable / shareable on its own — agents do not need to
  be in this repo (or visible to it) to be evaluated.

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

A reference implementation pattern: instantiate a fresh agent per game
inside `run_on_game`, run it on the supplied `game` object, then convert
your agent's internal metrics to `AgentRunResult` (mapping per-level
completion + action counts; the runner fills in baselines).

## CLI usage

### List all benchmark games

```bash
cd arc-witness-envs
python -m bench --list-games
```

### Run a custom agent against the benchmark

```bash
PYTHONPATH=path/to/arc-witness-envs python -m bench \
    --agent some.module:AgentClass \
    --agent-args '{"config": {...}}' \
    --games tw01 tw02 \
    --max-levels 2 \
    -o eval_results/myagent.json
```

If your agent has its own configuration mechanism (YAML files, env vars,
etc.), it's usually cleaner to write a thin agent-side wrapper script that
loads your config, constructs your agent, and calls
`bench.runner.run_batch` programmatically — see "Programmatic usage"
below. The CLI here is best for stateless / config-light agents.

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

Agent-side wrappers may augment this JSON with their own legacy fields
(e.g., to preserve backward compatibility with pre-existing analysis
scripts). The bench output above is the authoritative shape; consumers
that only read bench fields can ignore any additional keys an agent
chooses to write.

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
- ✅ **Multi-run / multi-seed evaluation** (2026-05-04) —
  `run_batch_multi_seed()` runs the agent across multiple seeds and
  aggregates per-game results via MAX (matching
  `arc_agi.scorecard.EnvironmentScoreList.score = max(...)`). Per-run
  details (scores, elapsed, errors, best_run_idx) preserved in
  `GameReportEntry.legacy`. CLI flags: `--n-runs N` for sequential seeds
  `0..N-1`, or `--seeds 0 7 42` for explicit list. Single-seed shortcut
  (`len(seeds) == 1`) delegates to `run_batch` for identical output shape.

### Multi-run usage

```bash
# 5 sequential seeds (0..4), best-of-5 per game
python -m bench --agent your.module:Agent --n-runs 5

# Explicit seed list
python -m bench --agent your.module:Agent --seeds 0 7 42 100

# In your output JSON:
# games[i].score          → MAX-aggregated WitnessScore
# games[i].legacy.per_run_scores  → list of per-run WitnessScore dumps
# games[i].legacy.best_run_idx    → index into seeds[] of best run
# run_metadata.seeds              → [0, 7, 42, 100]
# run_metadata.n_runs             → 4
```

## Open / deferred items

- **Per-level resets**. Currently per-game only. Add when agent-internal
  reset accounting is needed (e.g., to detect reset-loop bugs per level).
- **`level_tags` / `private_tags`** aggregation. Fields present in
  `WitnessGameInfo` but not yet populated in metadata.json.
- **ARC-AGI-3 SDK games** (`ls20`, `ft09`, `vc33`) are out of scope for
  this CLI. Those use the official `arc_agi.Arcade` env wrapper directly;
  evaluating against them is an agent-side concern. A future enhancement
  could add an `--include-arc-sdk-games` knob and route to
  `arc_agi.scorecard.EnvironmentScoreCalculator`.
- **Parallel multi-run execution.** Current `run_batch_multi_seed` is
  sequential (seed-major). For independent stateless agents it could
  parallelize, but agents that share state (e.g., persistent caches)
  would break. Out of scope for v1.
