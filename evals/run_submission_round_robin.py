#!/usr/bin/env python3
"""Evaluate submit-ready policies with the official starter-kit referee.

This runner intentionally evaluates only policies that speak the course stdin /
stdout protocol. It uses the unmodified referee copied from the official starter
kit in ``submission/referee.py``; unlike the JavaScript runner, its games have
the same observations, clocks and termination rules as a course submission.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFEREE = ROOT / "submission" / "referee.py"

sys.path.insert(0, str(ROOT / "evals"))
from catalog import load_policies  # noqa: E402


def wilson(points: float, games: int, z: float = 1.96) -> tuple[float, float]:
    if not games:
        return 0.0, 1.0
    rate = points / games
    denominator = 1 + z * z / games
    center = (rate + z * z / (2 * games)) / denominator
    half = z * ((rate * (1 - rate) + z * z / (4 * games)) / games) ** 0.5 / denominator
    return max(0.0, center - half), min(1.0, center + half)


def command(policy: dict, seed: int) -> list[str]:
    script = policy["run_sh"]
    launchers = (
        ("bot.py", [sys.executable, str(ROOT / "submission" / "bot.py")]),
        ("external_adapter.mjs", ["node", str(ROOT / "evals" / "external_adapter.mjs")]),
        ("misty_adapter.py", [sys.executable, str(ROOT / "evals" / "misty_adapter.py")]),
    )
    for marker, argv in launchers:
        if marker in script:
            args = script.split(marker, 1)[1].strip().split()
            return [*argv, *args, "--seed", str(seed)]
    raise SystemExit(f"{policy['id']} run.sh does not launch bot.py, external_adapter.mjs, or misty_adapter.py")


def result_score(result: str, side: str) -> float:
    if result == "1/2-1/2":
        return 0.5
    return float((result == "1-0") == (side == "white"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-plies", type=int, default=1000)
    parser.add_argument("--base-time", type=float, default=180)
    parser.add_argument("--increment", type=float, default=2)
    parser.add_argument("--include", action="append", default=[], help="Only play pairs that include this policy id. Repeat for several.")
    parser.add_argument("--run-id", default=f"submission-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}")
    args = parser.parse_args()
    if args.games < 2:
        raise SystemExit("--games must be at least 2")
    policies = [p for p in load_policies() if p.get("status") == "ready" and p.get("run_sh")]
    if len(policies) < 2:
        raise SystemExit("Need at least two submit-ready policies")
    pairs = list(combinations(policies, 2))
    if args.include:
        wanted = set(args.include)
        missing = wanted - {policy["id"] for policy in policies}
        if missing:
            raise SystemExit("No ready run.sh for " + ", ".join(sorted(missing)))
        pairs = [(left, right) for left, right in pairs if left["id"] in wanted or right["id"] in wanted]
    if not pairs:
        raise SystemExit("No pairs to play")
    run_dir = ROOT / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict] = []
    for left, right in pairs:
        for game in range(args.games):
            white, black = (left, right) if game % 2 == 0 else (right, left)
            replay = run_dir / f"{left['id']}--{right['id']}--{game:03d}.json"
            seed = (game + 1) * 1_000_003
            invocation = [
                sys.executable, str(REFEREE), "--trusted-local",
                "--white", " ".join(command(white, seed)),
                "--black", " ".join(command(black, seed + 1)),
                "--white-name", white["id"], "--black-name", black["id"],
                "--base-time", str(args.base_time), "--increment", str(args.increment),
                "--max-plies", str(args.max_plies), "--output", str(replay),
            ]
            subprocess.run(invocation, check=True)
            game_data = json.loads(replay.read_text())
            print(f"{replay.name}  {game_data['result']}  {game_data['reason']}", flush=True)
            records.append({
                "game": game, "white": white["id"], "black": black["id"],
                "result": game_data["result"], "reason": game_data["reason"],
                "replay": replay.name,
                "scores": {white["id"]: result_score(game_data["result"], "white"), black["id"]: result_score(game_data["result"], "black")},
            })
    leaderboard = []
    played = [policy for policy in policies if any(policy["id"] in record["scores"] for record in records)]
    for policy in played:
        scores = [record["scores"][policy["id"]] for record in records if policy["id"] in record["scores"]]
        points = sum(scores)
        low, high = wilson(points, len(scores))
        leaderboard.append({"policy_id": policy["id"], "games": len(scores), "points": points, "score": points / len(scores), "ci95_low": low, "ci95_high": high})
    leaderboard.sort(key=lambda row: row["score"], reverse=True)
    summary = {"run_id": args.run_id, "created_at": datetime.now(timezone.utc).isoformat(), "games_per_pair": args.games, "base_time": args.base_time, "increment": args.increment, "max_plies": args.max_plies, "leaderboard": leaderboard, "matches": records}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "leaderboard": leaderboard}, indent=2))


if __name__ == "__main__":
    main()
