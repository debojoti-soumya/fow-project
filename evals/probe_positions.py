#!/usr/bin/env python3
"""Show four Fog-of-War positions that a match score does not isolate.

A round robin reports one number for a whole game. These positions each check
one rule that differs from ordinary chess. A policy can win almost every game
and still fail one of them.

1. Hidden pawn blocker. The square in front of a pawn is unseen, so advancing
   is not a legal observation-consistent move.
2. Pinned piece. Moving the knight off the king's file is legal, and it loses
   at once because the rook behind it can then capture the king.
3. En passant. The capture appears only on the move after the opponent's
   two-square pawn push, and only if that push is the unique explanation.
4. Castling onto an attacked square. Castling into attack is legal. Landing
   on the attacked square still loses immediately.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
from bot import POLICIES, ObservationTracker, choose_move  # noqa: E402


def square(file: str, rank: int) -> int:
    return chess.square(ord(file) - 97, rank - 1)


def view(placed: dict[int, str]) -> str:
    cells = ["?"] * 64
    for index, char in placed.items():
        cells[index] = char
    return "".join(cells)


def tracker(first: str, second: str | None = None) -> ObservationTracker:
    state = ObservationTracker(chess.WHITE)
    state.observe(first)
    if second is not None:
        state.observe(second)
    return state


def hidden_blocker():
    state = tracker(view({square("e", 2): "P", square("e", 3): "?"}))
    illegal = [move.uci() for move in state.legal_moves() if move.uci() in {"e2e3", "e2e4"}]
    return {
        "title": "Hidden pawn blocker",
        "detail": "e3 is unseen, so the pawn on e2 cannot step forward.",
        "state": state,
        "bad": set(),
        "illegal": illegal,
    }


def pinned_knight():
    visible = {square("e", rank): "-" for rank in range(3, 8)}
    visible.update({square("e", 1): "K", square("e", 2): "N", square("e", 8): "r"})
    for name in ("c1", "g1", "d1", "f1", "c3", "d2", "f2", "g3", "d4", "f4"):
        visible[square(name[0], int(name[1]))] = "-"
    state = tracker(view(visible))
    return {
        "title": "Pinned piece that loses",
        "detail": "The rook on e8 is visible. Every knight move off e2 opens the king and loses immediately.",
        "state": state,
        "bad": {move.uci() for move in state.legal_moves() if move.from_square == square("e", 2)},
        "illegal": [],
    }


def en_passant():
    before = view({square("e", 5): "P", square("d", 7): "p"})
    after = view({square("e", 5): "P", square("d", 5): "p", square("d", 6): "-", square("d", 7): "-"})
    state = tracker(before, after)
    return {
        "title": "En passant",
        "detail": "Black's only consistent last move is d7-d5. White can capture it with e5d6 on this move only.",
        "state": state,
        "bad": set(),
        "goal": "e5d6",
        "illegal": [],
    }


def castle_into_attack():
    state = tracker(view({
        square("e", 1): "K", square("h", 1): "R", square("f", 1): "-", square("g", 1): "-",
        square("g", 8): "r", **{square("g", rank): "-" for rank in range(2, 8)},
    }))
    return {
        "title": "Castling onto an attacked square",
        "detail": "e1g1 is legal. The rook on g8 attacks g1, so the move loses immediately.",
        "state": state,
        "bad": {"e1g1"},
        "illegal": [],
    }


def main() -> None:
    for position in (hidden_blocker(), pinned_knight(), en_passant(), castle_into_attack()):
        print(position["title"])
        print(position["detail"])
        if position["illegal"]:
            print("illegal advances still offered: " + " ".join(position["illegal"]))
        else:
            print("illegal advances offered: none")
        legal = " ".join(move.uci() for move in position["state"].legal_moves()) or "(none)"
        print("legal: " + legal)
        for name in POLICIES:
            chosen = choose_move(position["state"], random.Random(1), name)
            uci = chosen.uci() if chosen else "(none)"
            if uci in position["bad"]:
                verdict = "loses immediately"
            elif chosen is None:
                verdict = "no legal move"
            elif position.get("goal") and name == "capture-greedy" and uci != position["goal"]:
                verdict = "missed " + position["goal"]
            elif position.get("goal") and uci == position["goal"]:
                verdict = "plays the capture"
            else:
                verdict = "avoids the losing move" if position["bad"] else "ok"
            print(f"  {name}: {uci} ({verdict})")
        print()


if __name__ == "__main__":
    main()
