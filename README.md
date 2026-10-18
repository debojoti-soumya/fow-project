# Fog of War Lab

A local match server and a Cloudflare-hosted arena for Fog-of-War chess. Policies play through the course referee. Replays, Elo, and move clocks live in D1. The site only reads that database.

Live arena: [fow-lab.debojotisoumya.workers.dev](https://fow-lab.debojotisoumya.workers.dev)

```
site/          arena UI, worker, and D1 migrations
evals/         register, play, probe, and publish
external/      pinned public engines
runs/          referee replays, one directory per run
submission/    course-protocol bot and the starter-kit referee
```

## Setup

```bash
git submodule update --init --recursive
python3 -m pip install chess
```

The referee imports `chess` (python-chess). Node 18+ is required for the Obscuro agents. Misty v1 also needs `pip install misty-chess`, Stockfish on `PATH`, and the `fow_rust` extension. `external-misty-tier1` needs only the Python package.

`python3 evals/refresh_arena.py --dry-run` prints the catalog and the play command and writes nothing.

## Everyday commands

| Command | What it does |
|---|---|
| `python3 evals/probe_positions.py` | Four cheap rule checks before a long run: hidden pawn blocker, pin that loses, en passant, castle onto an attacked square |
| `python3 evals/run_pair.py --white local-develop --black local-safe --games 4` | One color-swapped matchup. Add `--publish` to reload D1 |
| `python3 evals/run_submission_round_robin.py --games 4 --include external-misty-v1` | Pairs that include that id. `--games` must be even and at least 2 |
| `python3 evals/refresh_arena.py --games 8` | Register every catalog row, play every ready pair, publish |
| `python3 evals/import_runs.py` | Replace arena rows from `runs/` and recompute Elo |
| `python3 evals/summarize_times.py` | White and black move times from the replays on disk |

`npm run arena:refresh`, `npm run eval:pair`, `npm run eval:times`, and `npm run eval:probe` call the same scripts. A full refresh plays every ready policy, so cap it (`--max-plies 40 --base-time 30`) when Obscuro or Misty is in the catalog. Those agents are limited to 400 ms per move inside the adapter.

Replays land in `runs/<run-id>/`. A game that hits `--max-plies` is stored as a draw. `import_runs.py` keeps a game when every frame has a 64-character board. Result-only logs stay on disk and stay off the arena.

## Add a bot

A Python policy is a `--policy` flag in `submission/bot.py` plus one row in `evals/policies.py`. The flags that already play are `random`, `capture-greedy`, `develop`, `pawn-storm`, `check-seek`, and `safe`.

```bash
python3 evals/add_bot.py --sync
python3 evals/add_bot.py --id local-example --policy develop --description "A second seat for the develop policy"
```

A public Node engine sets `launch` to `evals/external_adapter.mjs` instead of a `--policy` flag. Misty sets `launch` to `evals/misty_adapter.py`. `add_bot.py --sync` upserts those rows into D1. The next `refresh_arena.py` plays every row whose `run.sh` is ready.

The course protocol is: read `fow`, read the color and clock line, print `ready`, store each 64-character observation, and print `move <uci>` only after the clock prompt. Index 0 is a1.

## What the site shows

- **Arena** opens a replay at ply 0. White, Black, and the true board come from the stored frames. Each game charts white and black move time separately, plus the cumulative clock and the mean, median, max, and total for each side.
- **Leaderboard** has standings, a result matrix, Elo history, and average time spent with white and with black.
- **Games** filters by player and outcome and splits clock time by color.
- **Policies** lists the catalog. A row with a ready `run.sh` can be played. Other rows stay visible until they can speak the protocol.

Elo starts at 1500 with K = 24. Games are applied in `created_at` order, then file order. Import replaces the run, game, move, and rating tables.

## Public engines already wired

| Id | Engine |
|---|---|
| `external-opowell-chess-agent` | Obscuro particle alpha-beta |
| `external-opowell-obscuro-search` | Obscuro equilibrium search |
| `external-opowell-paper-design` | Zhang and Sandholm design point, depth-1 leaves, uniform belief |
| `local-gtcfr-leaf1` | Same search with the leaf evaluator fixed at depth 1 |
| `external-misty-v1` | Misty profile v1.0 |
| `external-misty-tier1` | Misty material-particle policy |
| `external-opowell-random-legal` | Seeded uniform legal-move control |

ReconChess, ImpCatcher, and reconblindchess stay off this board. Details are in `external/ADAPTERS.md`.

Target machine for a course archive: offline Linux, 2 cores, 4 GiB RAM, five-minute builds, 180s + 2s per move. The Node and Misty agents play in this lab. A course upload still needs a runtime that includes those dependencies.
