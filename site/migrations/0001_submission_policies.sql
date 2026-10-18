DROP TABLE IF EXISTS leaderboard_entries;
DROP TABLE IF EXISTS policies;

CREATE TABLE policies (
  id TEXT PRIMARY KEY,
  archive_name TEXT NOT NULL UNIQUE,
  run_sh TEXT,
  build_sh TEXT,
  source_entry TEXT NOT NULL,
  weights TEXT,
  status TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  engine TEXT NOT NULL DEFAULT '',
  entry TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE leaderboard_entries (
  id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  games INTEGER NOT NULL,
  win_rate REAL NOT NULL,
  ci_low REAL NOT NULL,
  ci_high REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(policy_id) REFERENCES policies(id)
);

INSERT INTO policies (id, archive_name, run_sh, build_sh, source_entry, weights, status, description, engine, entry) VALUES
('external-opowell-obscuro-search', 'external-opowell-obscuro-search.zip', NULL, NULL, 'ChessObscuroAgent', NULL, 'baseline', 'Public fog-aware equilibrium-search agent, evaluated at the pinned submodule revision. Node is not in the course runtime, so this is not an uploadable archive.', 'opowell-obscuro-chess', 'ChessObscuroAgent'),
('external-opowell-chess-agent', 'external-opowell-chess-agent.zip', NULL, NULL, 'ChessAgent', NULL, 'baseline', 'Public heuristic particle-belief chess agent from the same compatible implementation. Node is not in the course runtime, so this is not an uploadable archive.', 'opowell-obscuro-chess', 'ChessAgent'),
('external-opowell-random-legal', 'external-opowell-random-legal.zip', '#!/bin/bash
set -euo pipefail
exec python3 -u bot.py --policy random
', NULL, 'bot.py', NULL, 'ready', 'Seeded uniform sampler over legal actions. Archive root is run.sh; the course runtime does not need build.sh or weights.', 'opowell-obscuro-chess', 'RandomLegal'),
('local-gtcfr-leaf1', 'local-gtcfr-leaf1.zip', NULL, NULL, 'GTCFRLeaf1', NULL, 'candidate', 'A resource-bounded GT-CFR/PCFR+ search ablation with a depth-1 leaf evaluator. It tests the paper''s search ingredients; it is not a reproduction of the original C++ agent, and Node is not in the course runtime.', 'opowell-obscuro-chess', 'GTCFRLeaf1'),
('external-misty-random', 'external-misty-random.zip', NULL, NULL, 'RandomStrategy', NULL, 'smoke-tested-not-deployable', 'Misty random-vs-random smoke test passed. The search engine requires an external Stockfish binary and its Rust extension, so it is not an uploadable course archive.', 'misty-dark-chess', 'RandomStrategy'),
('external-reconchess-random', 'external-reconchess-random.zip', NULL, NULL, 'RandomBot', NULL, 'smoke-tested-separate-ruleset', 'Built-in ReconChess random policy. Recon Chess includes a sensing phase, so it is a separate ruleset and not a Fog-of-War submission archive.', 'reconchess', 'RandomBot'),
('local-capture-greedy', 'local-capture-greedy.zip', '#!/bin/bash
set -euo pipefail
exec python3 -u bot.py --policy capture-greedy
', NULL, 'bot.py', NULL, 'ready', 'Official-protocol visible-capture and promotion priority control. Archive root is run.sh; the course runtime does not need build.sh or weights.', 'mit-fow-protocol', 'capture-greedy');
