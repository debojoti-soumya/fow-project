#!/usr/bin/env python3
"""Print per-player move times for referee runs on disk.

    python3 evals/summarize_times.py
    python3 evals/summarize_times.py runs/submission-2026-10-18T02-47-18Z
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from import_runs import load_run  # noqa: E402


def consume(run: dict, buckets: dict) -> None:
    for game in run["games"]:
        for side, policy in (("white", game["white"]), ("black", game["black"])):
            samples = [move["seconds"] for move in game["moves"] if move["side"] == side and move["seconds"] is not None]
            bucket = buckets.setdefault(policy, {"games": 0, "white": [], "black": [], "max": 0.0})
            bucket["games"] += 1
            bucket[side].extend(samples)
            if samples:
                bucket["max"] = max(bucket["max"], max(samples))


def ms(values: list[float]) -> str:
    if not values:
        return "—"
    mean = sum(values) / len(values) * 1000
    ordered = sorted(values)
    mid = ordered[len(ordered) // 2] * 1000
    return f"{mean:7.2f} mean  {mid:7.2f} median  n={len(values)}"


def report(buckets: dict) -> None:
    if not buckets:
        raise SystemExit("No referee games with boards were found")
    print(f"{'policy':<36} {'games':>5}  white ms                         black ms")
    for policy, bucket in sorted(buckets.items()):
        print(f"{policy:<36} {bucket['games']:5d}  {ms(bucket['white']):<32} {ms(bucket['black'])}  max {bucket['max'] * 1000:.2f}")


def main() -> None:
    targets = [Path(arg) for arg in sys.argv[1:]] or sorted(path for path in (ROOT / "runs").iterdir() if path.is_dir())
    buckets: dict = {}
    for directory in targets:
        run = load_run(directory)
        if run:
            consume(run, buckets)
    report(buckets)


if __name__ == "__main__":
    main()
