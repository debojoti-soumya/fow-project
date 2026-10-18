CREATE TABLE policies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  family TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  branch TEXT NOT NULL DEFAULT '',
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
