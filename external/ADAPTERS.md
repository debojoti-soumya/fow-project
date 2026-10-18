# External policies and adapters

The policy source of truth is the hosted D1 catalog. Executable third-party
code is pinned under this directory as Git submodules. Raw games and score
summaries are stored in `runs/<run-id>/`.

## Compatible now

All entries below share the `opowell-obscuro-chess` rules and are eligible for
the same round-robin command.

- `external-opowell-obscuro-search` — public search agent, at the pinned
  submodule revision.
- `external-opowell-chess-agent` — public particle-belief chess agent.
- `external-opowell-random-legal` — seeded uniform legal-action control. The
  upstream repository has `UNIFORM_PRIOR` for belief modeling but does not ship
  a random *playing* agent, so this small adapter supplies that missing control.
- `external-opowell-paper-design` — the Zhang and Sandholm design point of the
  same agent, through `evals/external_adapter.mjs --preset paper-design`.
- `local-gtcfr-leaf1` — the same search with the leaf evaluator fixed at depth 1.
- `external-misty-v1` and `external-misty-tier1` — Misty's published fog-of-war
  profiles, through `evals/misty_adapter.py`. The package is `misty-chess`;
  profile v1.0 also needs Stockfish and the `fow_rust` extension.

## Research watchlist (not cross-scored)

- **1-KLSS dark-chess agent** — the earlier Zhang–Sandholm approach. The paper
  describes a depth-limited 1-KLSS implementation, but no public source release
  was found. It is a research target, not an importable baseline.
- [Misty](https://github.com/brianhliou/misty) — profiles `v1.0` and `tier1` are
  wrapped above. The old `external-misty-random` row stays a smoke record. The
  engine is GPL and, without its Rust extension, the belief update is the slow
  Python path.
- [ImpCatcher](https://github.com/anoojpatel/ImpCatcher) — a Julia
  Dark/FoW-chess project. It could not be run locally because Julia is absent;
  its declared dependency set also includes CUDA, so it does not meet the
  current one-CPU / 2 GiB target without a major adapter.
- [Evhevh/Fog-of-War-Chess](https://github.com/Evhevh/Fog-of-War-Chess) — an
  MIT Python rules engine. Its documented three-move smoke sequence completed,
  but it is not a player policy and deliberately omits several rules; useful as
  a reference only.
- [ReconChess](https://github.com/reconnaissanceblindchess/reconchess) — its
  built-in `RandomBot` completed a local random-vs-random match. Its sensing
  phase is a different game contract, so it belongs to a separate leaderboard.
- [ceremonious/reconblindchess](https://github.com/ceremonious/reconblindchess)
  — an experimental neural belief/policy implementation for Recon Chess. It
  requires legacy Keras/TensorFlow and ships no usable trained policy, so it is
  also kept off the runnable suite.

Never score an item from this watchlist beside a compatible policy until its
adapter and rule equivalence are reviewed.
