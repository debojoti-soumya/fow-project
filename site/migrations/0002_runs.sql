CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  engine TEXT NOT NULL DEFAULT '',
  engine_revision TEXT NOT NULL DEFAULT '',
  games_per_pair INTEGER,
  max_turns INTEGER,
  game_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE games (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  white_id TEXT NOT NULL,
  black_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  winner_id TEXT,
  reason TEXT NOT NULL DEFAULT '',
  plies INTEGER NOT NULL DEFAULT 0,
  white_score REAL NOT NULL,
  black_score REAL NOT NULL,
  white_time_s REAL,
  black_time_s REAL,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE moves (
  game_id TEXT NOT NULL,
  ply INTEGER NOT NULL,
  side TEXT NOT NULL,
  uci TEXT,
  seconds REAL,
  clock_after REAL,
  view TEXT,
  PRIMARY KEY (game_id, ply),
  FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE ratings (
  policy_id TEXT PRIMARY KEY,
  elo REAL NOT NULL,
  games INTEGER NOT NULL,
  points REAL NOT NULL,
  wins INTEGER NOT NULL,
  draws INTEGER NOT NULL,
  losses INTEGER NOT NULL,
  avg_plies REAL NOT NULL,
  avg_move_s REAL,
  max_move_s REAL,
  total_time_s REAL,
  FOREIGN KEY (policy_id) REFERENCES policies(id)
);

CREATE TABLE rating_points (
  policy_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  elo REAL NOT NULL,
  PRIMARY KEY (policy_id, seq)
);

CREATE INDEX games_by_run ON games(run_id, ordinal);
