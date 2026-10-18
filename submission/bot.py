#!/usr/bin/env python3
"""Official-protocol Fog of War Chess submission bot.

This is derived from the supplied MIT 6.7980 uniform-random starter and keeps
its exact observation-only move generator, including castling, en passant and
promotion handling. ``--policy`` selects a submission-safe policy without
changing the stdin/stdout protocol.
"""
from __future__ import annotations

import argparse
import random
import sys

import chess

from referee import FowBoard, fow_moves

OBSERVATION_CHARACTERS = frozenset("?-PNBRQKpnbrqk")


def infer_en_passant(previous: str | None, current: str, side: chess.Color):
    """Infer the EP target from the observations bracketing an opponent move.

    An eligible enemy pawn must have just arrived from its starting rank. A
    single push would have been visible on our pawn's capture diagonal in the
    previous observation. A capture would change one of our always-visible
    pieces. If a different enemy move merely exposed a stationary pawn, it
    would change an already-visible blocker elsewhere along the revealing ray.
    Comparing squares visible on both observations rules out that alternative.

    Unknown squares are never treated as evidence of occupancy or emptiness.
    The routine is called only on our turn, with the immediately preceding
    observation, so its history spans exactly the opponent's preceding move.
    """
    if previous is None:
        return None
    ours, enemy = ("P", "p") if side else ("p", "P")
    own_symbols = "PNBRQK" if side else "pnbrqk"
    if any(before != after and (before in own_symbols or after in own_symbols)
           for before, after in zip(previous, current)):
        # Own pieces are always observed. Losing one, even when its former
        # square becomes unseen, proves the opponent captured instead.
        return None
    pawn_rank, middle_rank, start_rank = (4, 5, 6) if side else (3, 2, 1)
    possible = []
    for file in range(8):
        target = chess.square(file, pawn_rank)
        middle = chess.square(file, middle_rank)
        start = chess.square(file, start_rank)
        if current[target] != enemy or current[middle] != "-":
            continue
        if not any(0 <= other < 8 and current[chess.square(other, pawn_rank)] == ours
                   for other in (file - 1, file + 1)):
            continue
        if previous[target] not in "?-" or previous[middle] not in "?-":
            continue
        if previous[start] not in ("?", enemy) or current[start] not in "?-":
            continue
        if any(before != "?" and after != "?" and before != after
               for square, (before, after) in enumerate(zip(previous, current))
               if square not in (start, target)):
            continue
        possible.append(middle)
    if len(possible) > 1:
        raise ValueError("Observations are inconsistent with a single opponent move")
    return possible[0] if possible else None


def candidates(current: str, side: chess.Color, rights: int,
               previous: str | None = None):
    """Return a board containing visible pieces only and the exact legal moves.

    Empty unseen squares in the temporary board are placeholders. A move may
    never land on or slide through an unseen square; the explicit mask checks
    below stop those placeholders from creating phantom moves.
    """
    if len(current) != 64 or not set(current) <= OBSERVATION_CHARACTERS:
        raise ValueError("Expected a 64-square FOW observation")
    if previous is not None and (len(previous) != 64 or
                                 not set(previous) <= OBSERVATION_CHARACTERS):
        raise ValueError("Expected a 64-square previous FOW observation")
    board = FowBoard(None)
    board.turn = side
    for square, char in enumerate(current):
        if char not in "?-":
            board.set_piece_at(square, chess.Piece.from_symbol(char))
    board.castling_rights = rights
    board.ep_square = infer_en_passant(previous, current, side)
    moves = []
    for move in fow_moves(board):
        if current[move.to_square] == "?":
            continue
        piece = board.piece_at(move.from_square)
        if piece.piece_type != chess.KNIGHT:
            if any(current[square] == "?" for square in
                   chess.SquareSet(chess.between(move.from_square, move.to_square))):
                continue
        if board.is_castling(move):
            rank = 0 if side else 7
            files = (5, 6) if move.to_square > move.from_square else (1, 2, 3)
            if any(current[chess.square(file, rank)] != "-" for file in files):
                continue
        moves.append(move)
    return board, moves


class ObservationTracker:
    """Remember own castling rights and the last two public-to-us observations."""

    def __init__(self, side: chess.Color, rights: int | None = None):
        self.side = side
        self.rank = 0 if side else 7
        self.king_start = chess.square(4, self.rank)
        self.rook_starts = (chess.square(0, self.rank), chess.square(7, self.rank))
        self.rights = (sum(chess.BB_SQUARES[square] for square in self.rook_starts)
                       if rights is None else rights)
        self.previous = None
        self.current = None

    def observe(self, view: str):
        if len(view) != 64 or not set(view) <= OBSERVATION_CHARACTERS:
            raise ValueError("Expected a 64-square FOW observation")
        self.previous, self.current = self.current, view
        king, rook = ("K", "R") if self.side else ("k", "r")
        if view[self.king_start] != king:
            self.rights = 0
        for square in self.rook_starts:
            if view[square] != rook:
                self.rights &= ~chess.BB_SQUARES[square]

    def legal_moves(self):
        if self.current is None:
            raise ValueError("No observation received")
        return candidates(self.current, self.side, self.rights, self.previous)[1]

    def record_move(self, move: chess.Move):
        if self.current is None:
            raise ValueError("No observation received")
        if self.current[move.from_square].lower() == "k":
            self.rights = 0
        self.rights &= ~chess.BB_SQUARES[move.from_square]


VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
POLICIES = ("random", "capture-greedy", "develop", "pawn-storm", "check-seek", "safe")


def path_visible(view: str, start: int, end: int) -> bool:
    return all(view[square] != "?" for square in chess.SquareSet(chess.between(start, end)))


def visible_attackers(board, view: str, square: int, color: chess.Color) -> list[int]:
    found = []
    for source in board.attackers(color, square):
        piece = board.piece_at(source)
        if piece is None:
            continue
        if piece.piece_type != chess.KNIGHT and not path_visible(view, source, square):
            continue
        found.append(source)
    return found


def capture_value(board, move) -> float:
    target = board.piece_at(move.to_square)
    capture = 10 * VALUES[target.piece_type] if target else 0
    promotion = 5 * VALUES[move.promotion] if move.promotion else 0
    return capture + promotion


def center_score(square: int) -> float:
    file_distance = abs(chess.square_file(square) - 3.5)
    rank_distance = abs(chess.square_rank(square) - 3.5)
    return 2 - (file_distance + rank_distance) / 4


def enemy_king(view: str, side: chess.Color):
    symbol = "k" if side else "K"
    for square, char in enumerate(view):
        if char == symbol:
            return square
    return None


def gives_visible_check(board, view: str, move, side: chess.Color) -> bool:
    king = enemy_king(view, side)
    if king is None:
        return False
    if move.to_square == king:
        return True
    clone = board.copy(stack=False)
    clone.push(move)
    return bool(visible_attackers(clone, view, king, side))


def policy_score(policy: str, board, view: str, move, side: chess.Color, rng: random.Random) -> float:
    """Score one legal move from the visible board only."""
    noise = rng.random() * 1e-6
    gained = capture_value(board, move)
    piece = board.piece_at(move.from_square)
    center = center_score(move.to_square)
    if policy == "capture-greedy":
        return gained + center + noise
    if policy == "develop":
        castle = 40 if board.is_castling(move) else 0
        home = chess.square_rank(move.from_square) == (0 if side else 7)
        minor = piece is not None and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and home
        queen = -6 if piece is not None and piece.piece_type == chess.QUEEN and home else 0
        attacked = 50 if visible_attackers(board, view, move.to_square, not side) else 0
        return castle + (8 + center if minor else 0) + gained + center + queen - attacked + noise
    if policy == "pawn-storm":
        if piece is not None and piece.piece_type == chess.PAWN:
            direction = 1 if side else -1
            advance = direction * (chess.square_rank(move.to_square) - chess.square_rank(move.from_square))
            return 6 * advance + gained + (4 if move.promotion else 0) + noise
        return gained * 0.25 + noise
    if policy == "check-seek":
        check = 25 if gives_visible_check(board, view, move, side) else 0
        return check + gained + center + noise
    if policy == "safe":
        hung = 12 if visible_attackers(board, view, move.to_square, not side) else 0
        return gained + center - hung + noise
    raise ValueError(f"Unknown policy {policy}")


def choose_move(tracker: ObservationTracker, rng: random.Random, policy: str):
    """Choose from the complete observation-consistent move list.

    Every policy sees only the current observation. ``random`` samples it.
    The others rank visible captures, development, pawn advances, checks, or
    squares that a visible enemy piece does not attack.
    """
    moves = tracker.legal_moves()
    if not moves:
        return None
    if policy == "random":
        return rng.choice(moves)
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy {policy}")
    board, _ = candidates(tracker.current, tracker.side, tracker.rights, tracker.previous)
    return max(moves, key=lambda move: policy_score(policy, board, tracker.current, move, tracker.side, rng))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--policy", choices=POLICIES, default="random")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    if sys.stdin.readline().strip().lower() != "fow":
        return
    header = sys.stdin.readline().split()
    if len(header) != 3 or header[0].lower() not in ("w", "b"):
        raise ValueError("Expected color, base time, and increment")
    tracker = ObservationTracker(header[0].lower() == "w")
    print("ready", flush=True)
    for raw in sys.stdin:
        line = raw.strip()
        if len(line) == 64 and set(line) <= OBSERVATION_CHARACTERS:
            tracker.observe(line)
            continue
        try:
            float(line)
        except ValueError:
            continue
        move = choose_move(tracker, rng, args.policy)
        if move is None:
            return
        tracker.record_move(move)
        print("move " + move.uci(), flush=True)


if __name__ == "__main__":
    main()
