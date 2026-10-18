#!/usr/bin/env python3
"""Play one pair of ready policies and optionally publish the run to D1.

This is the short loop. The full round robin remains
``run_submission_round_robin.py``.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFEREE = ROOT / "submission" / "referee.py"
sys.path.insert(0, str(ROOT / "evals"))
from catalog import load_policies  # noqa: E402
from import_runs import publish as publish_runs  # noqa: E402
from run_submission_round_robin import command, result_score, wilson  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--white", default="local-capture-greedy")
    parser.add_argument("--black", default="external-opowell-random-legal")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--max-plies", type=int, default=40)
    parser.add_argument("--base-time", type=float, default=30)
    parser.add_argument("--increment", type=float, default=1)
    parser.add_argument("--publish", action="store_true", help="Reload every run, including this one, into D1")
    parser.add_argument("--run-id", default=f"pair-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}")
    args = parser.parse_args()
    if args.games < 1:
        raise SystemExit("--games must be at least 1")
    catalog = {policy["id"]: policy for policy in load_policies() if policy.get("status") == "ready" and policy.get("run_sh")}
    missing = [name for name in (args.white, args.black) if name not in catalog]
    if missing:
        raise SystemExit("No ready run.sh for " + ", ".join(missing) + ". Register it with evals/add_bot.py")
    run_dir = ROOT / "runs" / args.run_id
    run_dir.mkdir(parents=True)
    records = []
    for game in range(args.games):
        white, black = (args.white, args.black) if game % 2 == 0 else (args.black, args.white)
        replay_path = run_dir / f"{white}--{black}--{game:03d}.json"
        seed = (game + 1) * 1_000_003
        subprocess.run([
            sys.executable, str(REFEREE), "--trusted-local",
            "--white", " ".join(command(catalog[white], seed)),
            "--black", " ".join(command(catalog[black], seed + 1)),
            "--white-name", white, "--black-name", black,
            "--base-time", str(args.base_time), "--increment", str(args.increment),
            "--max-plies", str(args.max_plies), "--output", str(replay_path),
        ], check=True)
        replay = json.loads(replay_path.read_text())
        records.append({
            "game": game, "white": white, "black": black,
            "result": replay["result"], "reason": replay["reason"],
            "plies": max(0, len(replay.get("frames") or []) - 1),
            "replay": replay_path.name,
            "scores": {white: result_score(replay["result"], "white"), black: result_score(replay["result"], "black")},
        })
    leaderboard = []
    for policy in dict.fromkeys((args.white, args.black)):
        scores = [record["scores"][policy] for record in records]
        points = sum(scores)
        low, high = wilson(points, len(scores))
        leaderboard.append({"policy_id": policy, "games": len(scores), "points": points, "score": points / len(scores), "ci95_low": low, "ci95_high": high})
    summary = {
        "run_id": args.run_id, "created_at": datetime.now(timezone.utc).isoformat(),
        "games_per_pair": args.games, "base_time": args.base_time, "increment": args.increment,
        "max_plies": args.max_plies, "leaderboard": leaderboard, "matches": records,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "leaderboard": leaderboard}, indent=2))
    if args.publish:
        publish_runs()


if __name__ == "__main__":
    main()
