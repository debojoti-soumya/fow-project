"""Load the policy catalog from the hosted D1 database."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY = (
    "SELECT id, archive_name, run_sh, build_sh, source_entry, weights, status, "
    "description, engine, entry FROM policies ORDER BY archive_name"
)


def load_policies() -> list[dict]:
    completed = subprocess.run(
        ["npx", "--yes", "wrangler", "d1", "execute", "fow-lab", "--remote", "--json", "--command", QUERY],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    start = completed.stdout.find("[")
    if start < 0:
        raise RuntimeError(completed.stderr.strip() or "Wrangler did not return policy rows")
    payload = json.loads(completed.stdout[start:])
    return payload[0]["results"]
