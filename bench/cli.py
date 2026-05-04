"""CLI for `python -m bench`.

Examples:
    python -m bench --list-games
    python -m bench --agent some.module:AgentClass --games tw01 tw02 -o out.json
    python -m bench --agent module:Factory --agent-args '{"config":...}' --max-levels 2

If your agent has a complex config mechanism (YAML files, env vars, etc.),
write a thin agent-side wrapper that loads config and calls
`bench.runner.run_batch` programmatically — this CLI is best for stateless
or config-light agents.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
from typing import Any, Optional

from .catalog import list_games
from .runner import run_batch, run_batch_multi_seed
from .types import AgentInfo


def _load_agent(spec: str, args: dict) -> Any:
    """Resolve `module.path:ClassOrFactory` and call it with `**args`."""
    if ":" not in spec:
        raise SystemExit(f"--agent must be 'module:Symbol', got {spec!r}")
    mod_path, _, name = spec.partition(":")
    mod = importlib.import_module(mod_path)
    obj = getattr(mod, name)
    return obj(**args) if callable(obj) else obj


def _format_progress(game_id: str, score, elapsed_s, err) -> str:  # type: ignore[no-untyped-def]
    if err:
        return f"  [{game_id}] ERROR: {err}  ({elapsed_s:.1f}s)"
    return (
        f"  [{game_id}] score={score.score:6.2f}  "
        f"levels={score.levels_completed}/{score.levels_total}  "
        f"actions={score.actions}  ({elapsed_s:.1f}s)"
    )


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m bench",
        description="Evaluate an agent against the witness benchmark (tw01-tw13).",
    )
    p.add_argument("--list-games", action="store_true", help="Print all game IDs and exit")
    p.add_argument("--agent", help="Agent factory: 'module.path:ClassOrFunc'")
    p.add_argument("--agent-args", default="{}", help="JSON kwargs passed to agent factory")
    p.add_argument("--games", nargs="+", default=None, help="Subset of games to run")
    p.add_argument("--seed", type=int, default=0,
                   help="Single-run seed (ignored if --n-runs/--seeds given)")
    p.add_argument("--n-runs", type=int, default=1,
                   help="Number of seeds to run; aggregates per-game via MAX")
    p.add_argument("--seeds", nargs="+", type=int, default=None,
                   help="Explicit seed list (overrides --n-runs)")
    p.add_argument("--max-levels", type=int, default=None)
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--output", "-o", default=None, help="Output JSON path")
    p.add_argument("--tag-breakdown", action="store_true",
                   help="Print per-tag aggregate score table")
    args = p.parse_args(argv)

    if args.list_games:
        for g in list_games():
            print(g)
        return 0

    if not args.agent:
        p.error("--agent is required (or use --list-games)")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    for noisy in ("openai", "httpcore", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        agent_args = json.loads(args.agent_args)
    except json.JSONDecodeError as e:
        p.error(f"--agent-args is not valid JSON: {e}")

    agent = _load_agent(args.agent, agent_args)

    # Resolve seed strategy: --seeds wins; else --n-runs N → range(N); else single --seed.
    if args.seeds is not None:
        seeds = list(args.seeds)
    elif args.n_runs > 1:
        seeds = list(range(args.n_runs))
    else:
        seeds = [args.seed]

    print(f"\nAgent: {args.agent}")
    print(f"Games: {args.games or 'ALL ' + str(len(list_games()))}")
    print(f"Seeds: {seeds} ({len(seeds)} run{'s' if len(seeds) > 1 else ''})\n")

    common_kwargs = dict(
        agent=agent,
        game_ids=args.games,
        max_levels=args.max_levels,
        verbose=args.verbose,
        agent_info=AgentInfo(name=args.agent, extras={"agent_args": agent_args}),
        run_metadata={"argv": sys.argv[1:] if argv is None else argv},
        on_game_done=lambda gid, score, elapsed, err: print(
            _format_progress(gid, score, elapsed, err), flush=True
        ),
    )

    if len(seeds) == 1:
        report = run_batch(seed=seeds[0], **common_kwargs)
    else:
        report = run_batch_multi_seed(seeds=seeds, **common_kwargs)

    out = args.output or f"bench_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w") as f:
        f.write(report.model_dump_json(indent=2, exclude_none=True))

    s = report.summary
    print(
        f"\n=== SUMMARY ===\n"
        f"  Games:           {s.successful_games}/{s.total_games}\n"
        f"  Levels:          {s.total_levels_completed}/{s.total_levels}\n"
        f"  Overall score:   {s.overall_score:.2f}\n"
        f"  First-N hits:    {dict(s.first_n_completed)}\n"
        f"  Total actions:   {s.total_actions}\n"
        f"  Total resets:    {s.total_resets}\n"
        f"  Wall time:       {s.total_elapsed_s:.1f}s\n"
        f"  Saved:           {out}"
    )

    if args.tag_breakdown and s.tag_scores:
        print_tag_breakdown(s.tag_scores)

    return 0


def print_tag_breakdown(tag_scores) -> None:  # type: ignore[no-untyped-def]
    """Print a per-tag table sorted by mean_score (descending)."""
    if not tag_scores:
        return
    print("\n=== TAG BREAKDOWN ===")
    print(f"{'Tag':<28}{'Games':>6}  {'Score':>7}  {'Solved':>8}  {'Games in tag'}")
    print("-" * 80)
    items = sorted(tag_scores.values(), key=lambda t: t.mean_score, reverse=True)
    for ts in items:
        solved = f"{ts.total_levels_completed}/{ts.total_levels}"
        gids = ",".join(ts.game_ids) if len(ts.game_ids) <= 6 else f"{ts.game_ids[0]}…+{len(ts.game_ids)-1}"
        print(
            f"{ts.tag:<28}{ts.total_games:>6}  {ts.mean_score:>7.2f}  "
            f"{solved:>8}  {gids}"
        )
