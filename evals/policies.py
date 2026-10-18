"""Ready-policy rows the lab site and the future match server both use.

A new bot is a ``--policy`` flag in ``submission/bot.py`` plus one entry here.
``add_bot.py`` writes that entry into D1. ``refresh_arena.py`` then plays every
ready row and publishes the replays.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_sh(policy: str) -> str:
    return (
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f"exec python3 -u bot.py --policy {policy}\n"
    )


def launch_script(row: dict) -> str:
    launch = row.get("launch")
    if not launch:
        return run_sh(row["policy"])
    program = "python3 -u" if launch.split()[0].endswith(".py") else "node"
    return "#!/bin/bash\nset -euo pipefail\nexec " + program + " " + launch + "\n"


# Ids already used by stored games stay stable. New bots use a local- prefix.
CATALOG = (
    {
        "id": "external-opowell-random-legal",
        "policy": "random",
        "entry": "RandomLegal",
        "description": "Seeded uniform sampler over legal actions. It is the control every other bot is measured against.",
    },
    {
        "id": "local-capture-greedy",
        "policy": "capture-greedy",
        "entry": "capture-greedy",
        "description": "Prefers a visible capture or promotion, then a move toward the center. It never looks through fog.",
    },
    {
        "id": "local-develop",
        "policy": "develop",
        "entry": "develop",
        "description": "Castles when the observation allows it and develops visible knights and bishops before the queen.",
    },
    {
        "id": "local-pawn-storm",
        "policy": "pawn-storm",
        "entry": "pawn-storm",
        "description": "Pushes and captures with pawns. Other pieces move only when a pawn move is unavailable or a capture is large.",
    },
    {
        "id": "local-check-seek",
        "policy": "check-seek",
        "entry": "check-seek",
        "description": "Prefers a move that attacks the visible enemy king, then a visible capture. An unseen king is not treated as a target.",
    },
    {
        "id": "local-safe",
        "policy": "safe",
        "entry": "safe",
        "description": "Takes visible material only when the landing square is not attacked by a visible enemy piece.",
    },
    {
        "id": "external-opowell-chess-agent",
        "launch": "evals/external_adapter.mjs --agent chess --difficulty 25",
        "source": "ChessAgent",
        "engine": "opowell-obscuro-chess",
        "entry": "ChessAgent",
        "description": "Public particle-belief chess agent from opowell/obscuro-chess, speaking the course protocol through evals/external_adapter.mjs.",
    },
    {
        "id": "external-opowell-obscuro-search",
        "launch": "evals/external_adapter.mjs --agent obscuro --difficulty 25 --budget-ms 400",
        "source": "ChessObscuroAgent",
        "engine": "opowell-obscuro-chess",
        "entry": "ChessObscuroAgent",
        "description": "Public Obscuro equilibrium search from opowell/obscuro-chess, capped at 400 ms per move so a match server can finish a round robin.",
    },
    {
        "id": "external-opowell-paper-design",
        "launch": "evals/external_adapter.mjs --agent obscuro --preset paper-design --difficulty 25 --budget-ms 400",
        "source": "ChessObscuroAgent",
        "engine": "opowell-obscuro-chess",
        "entry": "ZhangSandholmDesign",
        "description": "The same public Obscuro agent at the Zhang and Sandholm design point: depth-1 leaves, a uniform belief, and no fitted opponent model. The match clock still caps the search at 400 ms.",
    },
    {
        "id": "local-gtcfr-leaf1",
        "launch": "evals/external_adapter.mjs --agent obscuro --leaf-depth 1 --difficulty 25 --budget-ms 400",
        "source": "ChessObscuroAgent",
        "engine": "opowell-obscuro-chess",
        "entry": "GTCFRLeaf1",
        "description": "Public GT-CFR search with the leaf evaluator fixed at depth 1. The belief and opponent model stay at the shipped defaults, and each move is capped at 400 ms.",
    },
    {
        "id": "external-misty-v1",
        "launch": "evals/misty_adapter.py --profile v1.0 --budget-ms 400",
        "source": "EngineV2Strategy",
        "engine": "misty-chess",
        "entry": "MistyV1",
        "description": "Public Misty fog-of-war engine, profile v1.0, speaking the course protocol through evals/misty_adapter.py. Search is capped at 400 ms per move.",
    },
    {
        "id": "external-misty-tier1",
        "launch": "evals/misty_adapter.py --profile tier1 --budget-ms 400",
        "source": "Tier1Strategy",
        "engine": "misty-chess",
        "entry": "MistyTier1",
        "description": "Misty's material-particle fog policy. It scores visible material over a sampled belief and does not call Stockfish.",
    },
)


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upsert_sql(row: dict) -> str:
    script = launch_script(row)
    source = row.get("source", "bot.py")
    engine = row.get("engine", "mit-fow-protocol")
    return (
        "INSERT INTO policies (id, archive_name, run_sh, build_sh, source_entry, weights, status, description, engine, entry) VALUES ("
        f"{sql_text(row['id'])}, {sql_text(row['id'] + '.zip')}, {sql_text(script)}, '', {sql_text(source)}, '', 'ready', "
        f"{sql_text(row['description'])}, {sql_text(engine)}, {sql_text(row['entry'])}) "
        "ON CONFLICT(id) DO UPDATE SET archive_name=excluded.archive_name, run_sh=excluded.run_sh, "
        "source_entry=excluded.source_entry, status='ready', description=excluded.description, "
        "engine=excluded.engine, entry=excluded.entry;"
    )


def execute_sql(statements: list[str]) -> None:
    for statement in statements:
        completed = subprocess.run(
            ["npx", "--yes", "wrangler", "d1", "execute", "fow-lab", "--remote", "--json", "--command", statement],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        start = completed.stdout.find("[")
        if completed.returncode != 0 or start < 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Wrangler did not confirm the policy write")
        payload = json.loads(completed.stdout[start:])
        if not payload[0].get("success", True):
            raise RuntimeError(json.dumps(payload[0]))
