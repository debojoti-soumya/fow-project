#!/usr/bin/env python3
"""Register a ready bot in the lab catalog.

The match server will call this before a round robin. It does not play games.

Register every bot shipped in submission/bot.py:

    python3 evals/add_bot.py --sync

Register one more id that uses an existing policy flag:

    python3 evals/add_bot.py --id local-develop-2 --policy develop --description "Second develop seat"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "evals"))
from bot import POLICIES  # noqa: E402
from policies import CATALOG, upsert_sql, execute_sql  # noqa: E402


def rows_from_args(args: argparse.Namespace) -> list[dict]:
    if args.sync:
        return [dict(row) for row in CATALOG]
    if not args.id or not args.policy or not args.description:
        raise SystemExit("Pass --sync, or pass --id, --policy, and --description")
    if args.policy not in POLICIES:
        raise SystemExit(f"Unknown policy {args.policy}. Choices: {', '.join(POLICIES)}")
    if not args.id.replace("-", "").isalnum() or not args.id[0].isalpha():
        raise SystemExit("--id must start with a letter and use only letters, numbers, and hyphens")
    return [{"id": args.id, "policy": args.policy, "entry": args.entry or args.policy, "description": args.description}]


def register(rows: list[dict], dry_run: bool = False) -> None:
    statements = [upsert_sql(row) for row in rows]
    for row in rows:
        label = row.get("policy") or row.get("launch", "")
        print(f"ready  {row['id']}  {label}", flush=True)
    if dry_run:
        print("\n".join(statements))
        return
    execute_sql(statements)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Upsert every bot in the local catalog")
    parser.add_argument("--id", help="Catalog id, also the archive name without .zip")
    parser.add_argument("--policy", help=f"submission/bot.py policy ({', '.join(POLICIES)})")
    parser.add_argument("--entry", help="Short label stored on the policy row")
    parser.add_argument("--description", help="One sentence shown on the Policies tab")
    parser.add_argument("--dry-run", action="store_true", help="Print the SQL without writing to D1")
    args = parser.parse_args()
    register(rows_from_args(args), args.dry_run)


if __name__ == "__main__":
    main()
