#!/usr/bin/env python3
"""Register local bots, play a round robin, and publish replays.

This is the command the match server should run. It does not start a web
server. The website reads whatever this script has published to D1.

    python3 evals/refresh_arena.py --games 8
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from add_bot import register  # noqa: E402
from import_runs import publish  # noqa: E402
from policies import CATALOG  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=8, help="Games per pair, colors swapped each game")
    parser.add_argument("--max-plies", type=int, default=60)
    parser.add_argument("--base-time", type=float, default=30)
    parser.add_argument("--increment", type=float, default=1)
    parser.add_argument("--skip-register", action="store_true")
    parser.add_argument("--skip-play", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Show the catalog and the play command, then stop")
    args = parser.parse_args()
    if args.games < 2 or args.games % 2:
        raise SystemExit("--games must be an even number of at least 2 so each color is played equally")
    rows = [dict(row) for row in CATALOG]
    play = [
        sys.executable, str(ROOT / "evals" / "run_submission_round_robin.py"),
        "--games", str(args.games),
        "--max-plies", str(args.max_plies),
        "--base-time", str(args.base_time),
        "--increment", str(args.increment),
    ]
    if args.dry_run:
        register(rows, dry_run=True)
        print(" ".join(play))
        return
    if not args.skip_register:
        register(rows)
    if not args.skip_play:
        subprocess.run(play, cwd=ROOT, check=True)
    publish()
    print("https://fow-lab.debojotisoumya.workers.dev")


if __name__ == "__main__":
    main()
