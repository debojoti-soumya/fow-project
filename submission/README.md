# Submission format

Build upload-ready archives with:

```sh
python3 submission/build_archives.py
```

Ready rows in the D1 catalog become the archives. Each archive has `run.sh` at
its root and follows the official protocol: it reads `fow`, the color/time
line, sends `ready`, consumes every 64-character observation, and only prints
`move <uci>` after its clock prompt. `build.sh` and `weights/` are included
only when that row has them.

Generated archives:

- `external-opowell-random-legal.zip` — uniform legal-move control.
- `local-capture-greedy.zip` — visible-capture and promotion priority control.

The implementation is derived from the official GPL-2.0 starter’s
observation-only move generator; its license is included in every archive.

## Not packageable yet

The public Node agents and Misty profiles play in this lab through
`evals/external_adapter.mjs` and `evals/misty_adapter.py`. A course upload
still needs the course runtime, which does not include Node, Stockfish, or
Misty's Rust extension. ReconChess uses a sensing phase this protocol does
not have. Those rows stay cataloged here and are not course archives.
