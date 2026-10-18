#!/usr/bin/env python3
"""Load referee replays into D1 and recompute Elo from those games.

A game is imported only when its replay stores a board for every frame. Result
logs that have a winner and a ply count, but no position, stay in ``runs/`` and
are left out of the arena. Re-running this script replaces the run, game, move,
and rating rows.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
SQL_PATH = ROOT / "dist" / "runs.sql"
INITIAL_ELO = 1500.0
K_FACTOR = 24.0


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_num(value) -> str:
    if value is None:
        return "NULL"
    return f"{float(value):.6f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(int(value))


def expected(rating: float, opponent: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent - rating) / 400.0))


def move_rows(replay: dict, increment: float) -> list[dict]:
    frames = replay.get("frames") or []
    rows = []
    for index, frame in enumerate(frames):
        clocks = frame.get("clocks") or [None, None]
        ply = int(frame.get("ply") if frame.get("ply") is not None else index)
        uci = frame.get("move") or ""
        side = ""
        seconds = None
        clock_after = None
        if uci and index:
            side = "white" if ply % 2 == 1 else "black"
            slot = 0 if side == "white" else 1
            previous = frames[index - 1].get("clocks") or [None, None]
            clock_after = clocks[slot] if slot < len(clocks) else None
            if previous[slot] is not None and clock_after is not None:
                seconds = max(0.0, float(previous[slot]) - (float(clock_after) - increment))
        rows.append({
            "ply": ply,
            "side": side,
            "uci": uci,
            "seconds": seconds,
            "clock_after": clock_after,
            "view": ((frame.get("white") if side != "black" else frame.get("black")) or "")[:64] or None,
            "clock_white": clocks[0] if clocks else None,
            "clock_black": clocks[1] if len(clocks) > 1 else None,
            "white_view": (frame.get("white") or "")[:64] or None,
            "black_view": (frame.get("black") or "")[:64] or None,
            "board": (frame.get("board") or "")[:64] or None,
        })
    return rows


def parse_match(row: dict, ordinal: int, replay: dict | None, increment: float) -> dict:
    result = row.get("result")
    if isinstance(result, dict):
        outcome = result.get("outcome") or "draw"
        reason = result.get("reason") or row.get("reason") or ""
        winner = result.get("winnerId")
    else:
        outcome = {"1-0": "win", "0-1": "win", "1/2-1/2": "draw"}.get(result, "draw")
        reason = row.get("reason") or ""
        winner = row["white"] if result == "1-0" else row["black"] if result == "0-1" else None
    white, black = row["white"], row["black"]
    scores = row.get("scores") or {}
    moves = move_rows(replay, increment) if replay else []
    def spent(side: str):
        taken = [move["seconds"] for move in moves if move["side"] == side and move["seconds"] is not None]
        return sum(taken) if taken else None
    return {
        "ordinal": ordinal,
        "white": white,
        "black": black,
        "outcome": outcome,
        "winner": winner,
        "reason": reason,
        "plies": int(row.get("plies") or (len(moves))),
        "white_score": float(scores.get(white, 0.5 if outcome == "draw" else 1 if winner == white else 0)),
        "black_score": float(scores.get(black, 0.5 if outcome == "draw" else 1 if winner == black else 0)),
        "white_time": spent("white"),
        "black_time": spent("black"),
        "moves": moves,
    }


def load_run(directory: Path) -> dict | None:
    summary_path = directory / "summary.json"
    if not summary_path.exists():
        return None
    summary = json.loads(summary_path.read_text())
    increment = float(summary.get("increment") or 2)
    games = []
    ndjson = directory / "matches.ndjson"
    if ndjson.exists():
        for ordinal, line in enumerate(line for line in ndjson.read_text().splitlines() if line.strip()):
            games.append(parse_match(json.loads(line), ordinal, None, increment))
    else:
        for ordinal, row in enumerate(summary.get("matches") or []):
            replay = None
            replay_name = row.get("replay")
            if replay_name and (directory / replay_name).exists():
                replay = json.loads((directory / replay_name).read_text())
                row = dict(row)
                row["plies"] = max(0, len(replay.get("frames") or []) - 1)
            games.append(parse_match(row, ordinal, replay, increment))
    games = [game for game in games if any(move.get("board") and len(move["board"]) == 64 for move in game["moves"])]
    if not games:
        return None
    engine = ""
    revision = summary.get("engine_revision") or ""
    if ndjson.exists():
        first = json.loads(next(line for line in ndjson.read_text().splitlines() if line.strip()))
        engine = first.get("engine") or ""
        revision = first.get("engine_revision") or revision
    elif games:
        engine = "mit-fow-protocol"
    return {
        "id": summary.get("run_id") or directory.name,
        "created_at": summary.get("created_at") or "",
        "engine": engine,
        "engine_revision": revision,
        "games_per_pair": summary.get("games_per_pair"),
        "max_turns": summary.get("max_turns") or summary.get("max_plies"),
        "games": games,
    }


def rate(runs: list[dict]) -> tuple[dict, list[tuple]]:
    ratings = {}
    history = []
    sequence = 0
    totals = {}
    for run in runs:
        for game in run["games"]:
            for policy, score, plies, spent in (
                (game["white"], game["white_score"], game["plies"], game["white_time"]),
                (game["black"], game["black_score"], game["plies"], game["black_time"]),
            ):
                bucket = totals.setdefault(policy, {"games": 0, "points": 0.0, "wins": 0, "draws": 0, "losses": 0, "plies": 0, "move_seconds": [], "time": 0.0})
                bucket["games"] += 1
                bucket["points"] += score
                bucket["plies"] += plies
                bucket["wins"] += score == 1
                bucket["draws"] += score == 0.5
                bucket["losses"] += score == 0
                if spent is not None:
                    bucket["time"] += spent
            white, black = ratings.setdefault(game["white"], INITIAL_ELO), ratings.setdefault(game["black"], INITIAL_ELO)
            ratings[game["white"]] = white + K_FACTOR * (game["white_score"] - expected(white, black))
            ratings[game["black"]] = black + K_FACTOR * (game["black_score"] - expected(black, white))
            for policy in (game["white"], game["black"]):
                sequence += 1
                history.append((policy, sequence, ratings[policy]))
            for move in game["moves"]:
                if move["seconds"] is None:
                    continue
                policy = game["white"] if move["side"] == "white" else game["black"]
                totals[policy]["move_seconds"].append(move["seconds"])
    rows = {}
    for policy, bucket in totals.items():
        samples = bucket["move_seconds"]
        rows[policy] = {
            "elo": ratings[policy],
            "games": bucket["games"],
            "points": bucket["points"],
            "wins": bucket["wins"],
            "draws": bucket["draws"],
            "losses": bucket["losses"],
            "avg_plies": bucket["plies"] / bucket["games"],
            "avg_move_s": sum(samples) / len(samples) if samples else None,
            "max_move_s": max(samples) if samples else None,
            "total_time_s": bucket["time"] if samples else None,
        }
    return rows, history


def statement(runs: list[dict], ratings: dict, history: list[tuple]) -> str:
    lines = [
        "DELETE FROM rating_points;",
        "DELETE FROM ratings;",
        "DELETE FROM moves;",
        "DELETE FROM games;",
        "DELETE FROM runs;",
    ]
    for run in runs:
        lines.append(
            "INSERT INTO runs (id, created_at, engine, engine_revision, games_per_pair, max_turns, game_count) VALUES ("
            f"{sql_text(run['id'])}, {sql_text(run['created_at'])}, {sql_text(run['engine'])}, {sql_text(run['engine_revision'])}, "
            f"{sql_num(run['games_per_pair'])}, {sql_num(run['max_turns'])}, {len(run['games'])});"
        )
        for game in run["games"]:
            game_id = f"{run['id']}--{game['ordinal']:04d}"
            lines.append(
                "INSERT INTO games (id, run_id, ordinal, white_id, black_id, outcome, winner_id, reason, plies, white_score, black_score, white_time_s, black_time_s) VALUES ("
                f"{sql_text(game_id)}, {sql_text(run['id'])}, {game['ordinal']}, {sql_text(game['white'])}, {sql_text(game['black'])}, "
                f"{sql_text(game['outcome'])}, {sql_text(game['winner']) if game['winner'] else 'NULL'}, {sql_text(game['reason'])}, {game['plies']}, "
                f"{sql_num(game['white_score'])}, {sql_num(game['black_score'])}, {sql_num(game['white_time'])}, {sql_num(game['black_time'])});"
            )
            for move in game["moves"]:
                lines.append(
                    "INSERT INTO moves (game_id, ply, side, uci, seconds, clock_after, view, clock_white, clock_black, white_view, black_view, board) VALUES ("
                    f"{sql_text(game_id)}, {move['ply']}, {sql_text(move['side'])}, {sql_text(move['uci'] or '')}, "
                    f"{sql_num(move['seconds'])}, {sql_num(move['clock_after'])}, {sql_text(move['view']) if move['view'] else 'NULL'}, "
                    f"{sql_num(move['clock_white'])}, {sql_num(move['clock_black'])}, "
                    f"{sql_text(move['white_view']) if move['white_view'] else 'NULL'}, "
                    f"{sql_text(move['black_view']) if move['black_view'] else 'NULL'}, "
                    f"{sql_text(move['board']) if move['board'] else 'NULL'});"
                )
    for policy, row in sorted(ratings.items()):
        lines.append(
            "INSERT INTO ratings (policy_id, elo, games, points, wins, draws, losses, avg_plies, avg_move_s, max_move_s, total_time_s) VALUES ("
            f"{sql_text(policy)}, {sql_num(row['elo'])}, {row['games']}, {sql_num(row['points'])}, {row['wins']}, {row['draws']}, {row['losses']}, "
            f"{sql_num(row['avg_plies'])}, {sql_num(row['avg_move_s'])}, {sql_num(row['max_move_s'])}, {sql_num(row['total_time_s'])});"
        )
    for policy, seq, elo in history:
        lines.append(f"INSERT INTO rating_points (policy_id, seq, elo) VALUES ({sql_text(policy)}, {seq}, {sql_num(elo)});")
    return "\n".join(lines) + "\n"


def collect() -> list[dict]:
    runs = [run for run in (load_run(path) for path in sorted(RUNS.iterdir()) if path.is_dir()) if run and run["games"]]
    runs.sort(key=lambda run: run["created_at"])
    return runs


def publish(dry_run: bool = False) -> None:
    runs = collect()
    if not runs:
        raise SystemExit("No runs with games were found")
    ratings, history = rate(runs)
    SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQL_PATH.write_text(statement(runs, ratings, history))
    print(f"{sum(len(run['games']) for run in runs)} games in {len(runs)} runs")
    for policy, row in sorted(ratings.items(), key=lambda item: item[1]["elo"], reverse=True):
        if row["avg_move_s"] is None:
            move = "no move clocks"
        elif row["avg_move_s"] < 0.05:
            move = f"{row['avg_move_s'] * 1000:.2f}ms/move"
        else:
            move = f"{row['avg_move_s']:.3f}s/move"
        print(f"{row['elo']:7.1f}  {policy}  {row['wins']}-{row['draws']}-{row['losses']}  {move}")
    if dry_run:
        print(SQL_PATH)
        return
    subprocess.run(["npx", "--yes", "wrangler", "d1", "execute", "fow-lab", "--remote", "--file", str(SQL_PATH)], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print Elo and write SQL without uploading")
    publish(parser.parse_args().dry_run)


if __name__ == "__main__":
    main()
