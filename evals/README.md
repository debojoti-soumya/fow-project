# Evaluation

`run_submission_round_robin.py` plays every ready archive with the official starter-kit referee. It swaps colors, records every replay, treats its cap as a draw, and computes a Wilson 95% interval.

```bash
python3 evals/add_bot.py --sync
python3 evals/refresh_arena.py --games 8
python3 evals/summarize_times.py
```

`add_bot.py` upserts ready rows from `policies.py`. `refresh_arena.py` is the
command a match server should run: register, play, and publish. Pass
`--skip-register` or `--skip-play` to run only part of that job.

Artifacts are written to `runs/<run-id>/`. A capped game is explicitly recorded as a draw; no score is silently discarded. Do not mix results from a different FoW rules implementation in the same leaderboard.

`import_runs.py` loads a game only when the replay contains a board on every frame, then replaces the arena rows and recomputes Elo. Logs that have a result and a ply count but no position are left on disk. The arena opens a loaded game at ply 0.

To introduce a policy, add its flag in `submission/bot.py` and a row in `policies.py`, then run `add_bot.py --sync`. A public Node engine instead sets `launch` to `evals/external_adapter.mjs`. The next `refresh_arena.py` plays every ready row. `external-opowell-random-legal` is the seeded legal-move control. `external-opowell-chess-agent` and `external-opowell-obscuro-search` are the pinned public agents. `external-opowell-paper-design` and `local-gtcfr-leaf1` are the other Obscuro configurations, and `external-misty-v1` / `external-misty-tier1` are the Misty fog profiles. Pass `--include <id>` to play only pairs that include that bot.

```bash
python3 evals/run_pair.py --games 4 --publish
python3 evals/probe_positions.py
python3 evals/package_policy.py
```

`run_pair.py` plays one matchup and can publish it. `package_policy.py` reloads the lab site from `runs/`. `probe_positions.py` checks four positions a match score does not isolate: a hidden pawn blocker, a pinned knight, an en-passant capture, and castling onto an attacked square.
