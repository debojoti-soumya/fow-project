#!/usr/bin/env python3
"""Course-protocol adapter for the public Misty fog-of-war engine.

The referee sends a 64-character observation, then a clock line. Misty wants
its own observation objects and a perspective view. This process keeps that
history and answers only after the clock prompt.

``--profile v1.0`` is Misty's published search profile. ``--profile tier1`` is
its material-particle policy, which does not call Stockfish.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
from bot import OBSERVATION_CHARACTERS, ObservationTracker, candidates  # noqa: E402

logging.getLogger("fow_chess").setLevel(logging.ERROR)


def observation_from_view(current: str, previous: str | None, side: chess.Color):
    from fow_chess import Observation

    own = "PNBRQK" if side else "pnbrqk"
    visible = chess.SquareSet(index for index, char in enumerate(current) if char != "?")
    pieces = {
        index: chess.Piece.from_symbol(char)
        for index, char in enumerate(current)
        if char not in "?-"
    }
    captured = None
    if previous is not None:
        gone = [index for index, (before, after) in enumerate(zip(previous, current)) if before in own and after not in own]
        if len(gone) == 1:
            captured = gone[0]
    landing = captured if captured is not None and current[captured] not in "?-" and current[captured] not in own else None
    return Observation(
        visibility_mask=visible,
        visible_pieces=pieces,
        own_capture_square=captured,
        opp_capture_landing_square=landing,
    )


def perspective(tracker: ObservationTracker, clock_seconds: float, increment: float):
    from fow_chess.selfplay import PerspectiveView

    board, moves = candidates(tracker.current, tracker.side, tracker.rights, tracker.previous)
    pieces = {square: piece for square, piece in board.piece_map().items()}
    visible = chess.SquareSet(index for index, char in enumerate(tracker.current) if char != "?")
    return PerspectiveView(
        perspective=tracker.side,
        own_legal_moves=moves,
        visible_squares=visible,
        visible_piece_map=pieces,
        clock_remaining_ms=max(0, int(clock_seconds * 1000)),
        increment_ms=int(increment * 1000),
    ), moves


def make_strategy(profile: str, seed: int, budget_ms: int):
    if profile == "tier1":
        from fow_chess import Tier1Strategy, material_evaluator

        return Tier1Strategy(lambda _view: material_evaluator(), target_n=48, max_eval_particles=12, seed=seed, mcts_rollouts=0)
    from fow_chess.engine_profile import PROFILES

    if profile not in PROFILES:
        raise SystemExit(f"Unknown Misty profile {profile}")
    return PROFILES[profile].build_strategy(
        seed=seed,
        time_budget_seconds=budget_ms / 1000,
        p_max_size=4000,
        iterations=80,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="v1.0")
    parser.add_argument("--budget-ms", type=int, default=400)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    if sys.stdin.readline().strip().lower() != "fow":
        return
    header = sys.stdin.readline().split()
    if len(header) != 3 or header[0].lower() not in ("w", "b"):
        raise SystemExit("Expected color, base time, and increment")
    side = header[0].lower() == "w"
    increment = float(header[2])
    strategy = make_strategy(args.profile, args.seed, args.budget_ms)
    strategy.reset(chess.WHITE if side else chess.BLACK)
    tracker = ObservationTracker(side)
    awaiting_own = False
    last_move = None
    started = False
    print("ready", flush=True)
    for raw in sys.stdin:
        line = raw.strip()
        if len(line) == 64 and set(line) <= OBSERVATION_CHARACTERS:
            if not started:
                tracker.observe(line)
                started = True
                continue
            observed = observation_from_view(line, tracker.current, tracker.side)
            try:
                if awaiting_own and last_move is not None:
                    strategy.observe_own_move(last_move, observed)
                    awaiting_own = False
                else:
                    strategy.observe_opp_move(observed)
            except Exception:
                # A reconstructed observation can empty Misty's exact belief.
                # Start again from the current view instead of exiting.
                strategy.reset(tracker.side)
                awaiting_own = False
            tracker.observe(line)
            continue
        try:
            remaining = float(line)
        except ValueError:
            continue
        if tracker.current is None:
            continue
        view, legal = perspective(tracker, remaining, increment)
        if not legal:
            return
        chosen = strategy.pick_move(view)
        if chosen not in legal:
            chosen = legal[0]
        tracker.record_move(chosen)
        last_move = chosen
        awaiting_own = True
        print("move " + chosen.uci(), flush=True)


if __name__ == "__main__":
    main()
