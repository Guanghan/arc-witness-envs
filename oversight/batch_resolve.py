"""CLI: re-solve unvalidated levels with the IDDFS solver to lift oracle
coverage on the weak games (tw12=4/160, tw03/tw11≈35%).

    python -m oversight.batch_resolve --game tw12 --timeout 30 --persist
    python -m oversight.batch_resolve --all --timeout 20            # dry-run all 13

Dry-run by default (reports only). --persist writes solution_actions / moves /
baseline / validated back into levels/<game>_levels.json. tw09/tw10 have no
solver and are skipped.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .oracle import WitnessOracle


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--game", help="game id (e.g. tw12)")
    p.add_argument("--all", action="store_true", help="all 13 witness games")
    p.add_argument("--timeout", type=float, default=20.0, help="per-level solver timeout (s)")
    p.add_argument("--persist", action="store_true", help="write solutions back to the levels JSON")
    args = p.parse_args(argv)

    games = [f"tw{i:02d}" for i in range(1, 14)] if args.all else ([args.game] if args.game else [])
    if not games:
        p.error("pass --game <id> or --all")

    orc = WitnessOracle()
    total = 0
    for g in games:
        rep = orc.batch_resolve(g, timeout=args.timeout, persist=args.persist)
        total += rep["solved"]
        tag = " [persisted]" if (args.persist and rep["solved"]) else ""
        print(f"{g}: attempted={rep['attempted']:4d} solved={rep['solved']:4d}{tag}")
    print(f"TOTAL newly solved: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
