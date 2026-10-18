#!/usr/bin/env node
// Course-protocol adapter for the pinned opowell/obscuro-chess agents.
//
// The referee speaks stdin/stdout. These agents speak FogChess observations.
// This process keeps castling rights and the previous observation, rebuilds the
// visible board, and asks the public agent for one move.

import { createInterface } from "node:readline";
import { FogChess } from "../external/opowell-obscuro-chess/src/FogChess.js";
import { ChessAgent } from "../external/opowell-obscuro-chess/src/ChessAgent.js";
import { ChessObscuroAgent } from "../external/opowell-obscuro-chess/src/ObscuroAgent.js";
import { loadPreset } from "../external/opowell-obscuro-chess/src/presets.js";
import { setOverrides } from "../external/opowell-obscuro-chess/src/config.js";

const FILES = "abcdefgh";
const TYPES = { p: "pawn", n: "knight", b: "bishop", r: "rook", q: "queen", k: "king" };
const PROMO = { queen: "q", rook: "r", bishop: "b", knight: "n" };

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = Math.imul(state ^ (state >>> 15), 1 | state);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function squareName(index) {
  return FILES[index % 8] + (Math.floor(index / 8) + 1);
}

function squareIndex(name) {
  return (Number(name[1]) - 1) * 8 + (name.charCodeAt(0) - 97);
}

function between(from, to) {
  const fileStep = Math.sign(to.charCodeAt(0) - from.charCodeAt(0));
  const rankStep = Math.sign(Number(to[1]) - Number(from[1]));
  const squares = [];
  let file = from.charCodeAt(0) + fileStep;
  let rank = Number(from[1]) + rankStep;
  while (file !== to.charCodeAt(0) || rank !== Number(to[1])) {
    squares.push(String.fromCharCode(file) + rank);
    file += fileStep;
    rank += rankStep;
  }
  return squares;
}

function observationMove(view, action) {
  if (view[squareIndex(action.to)] === "?") return false;
  if (action.type === "castle") {
    const squares = action.side === "kingside"
      ? [action.to, action.rookTo]
      : [action.rookTo, action.to, "b" + action.from[1]];
    return squares.every(square => view[squareIndex(square)] === "-");
  }
  const piece = view[squareIndex(action.from)].toLowerCase();
  if (piece !== "n" && between(action.from, action.to).some(square => view[squareIndex(square)] === "?")) return false;
  return true;
}

function inferEnPassant(previous, current, side) {
  if (!previous) return null;
  const white = side === "white";
  const ours = white ? "P" : "p";
  const enemy = white ? "p" : "P";
  const ownSymbols = white ? "PNBRQK" : "pnbrqk";
  for (let index = 0; index < 64; index += 1) {
    if (previous[index] !== current[index] && (ownSymbols.includes(previous[index]) || ownSymbols.includes(current[index]))) return null;
  }
  const pawnRank = white ? 4 : 3;
  const middleRank = white ? 5 : 2;
  const startRank = white ? 6 : 1;
  const possible = [];
  for (let file = 0; file < 8; file += 1) {
    const target = pawnRank * 8 + file;
    const middle = middleRank * 8 + file;
    const start = startRank * 8 + file;
    if (current[target] !== enemy || current[middle] !== "-") continue;
    const left = file > 0 && current[pawnRank * 8 + file - 1] === ours;
    const right = file < 7 && current[pawnRank * 8 + file + 1] === ours;
    if (!left && !right) continue;
    if (!"?-".includes(previous[target]) || !"?-".includes(previous[middle])) continue;
    if (!("?" + enemy).includes(previous[start]) || !"?-".includes(current[start])) continue;
    const changedElsewhere = [...previous].some((before, index) => {
      if (index === start || index === target) return false;
      const after = current[index];
      return before !== "?" && after !== "?" && before !== after;
    });
    if (changedElsewhere) continue;
    possible.push(squareName(middle));
  }
  return possible.length === 1 ? possible[0] : null;
}

function boardFromView(view) {
  const board = {};
  for (let index = 0; index < 64; index += 1) {
    const symbol = view[index];
    if (symbol === "?" || symbol === "-") continue;
    const ownerId = symbol === symbol.toUpperCase() ? "white" : "black";
    const type = TYPES[symbol.toLowerCase()];
    const position = squareName(index);
    board[position] = { id: `${ownerId[0]}${type[0]}${position}`, ownerId, type, position, alive: true };
  }
  return board;
}

function freshRights() {
  return { white: { kingSide: true, queenSide: true }, black: { kingSide: true, queenSide: true } };
}

function seeRights(rights, view) {
  for (const color of ["white", "black"]) {
    const back = color === "white" ? 0 : 7;
    const king = color === "white" ? "K" : "k";
    const rook = color === "white" ? "R" : "r";
    if (view[back * 8 + 4] !== "?" && view[back * 8 + 4] !== king) rights[color] = { kingSide: false, queenSide: false };
    if (view[back * 8] !== "?" && view[back * 8] !== rook) rights[color] = { ...rights[color], queenSide: false };
    if (view[back * 8 + 7] !== "?" && view[back * 8 + 7] !== rook) rights[color] = { ...rights[color], kingSide: false };
  }
}

function actionUci(action) {
  return action.from + action.to + (PROMO[action.payload?.promote] ?? "");
}

const agentName = arg("--agent", "chess");
const difficulty = Number(arg("--difficulty", "25"));
const budgetMs = Number(arg("--budget-ms", "400"));
const presetName = arg("--preset", "");
const leafDepth = arg("--leaf-depth", "");
const seed = arg("--seed", "");
if (seed) Math.random = mulberry32(Number(seed));
if (presetName) loadPreset(presetName);
const chessOverrides = { EXACT_BELIEF_TIME_GUARD_MS: Math.min(budgetMs, 200) };
if (leafDepth) {
  const depth = Number(leafDepth);
  chessOverrides.MAX_SF_DEPTH = depth;
  chessOverrides.CHESS_DIAL = { leafEval: { sfDepth: depth, cols: 0 } };
}
if (agentName !== "chess") setOverrides({ chess: chessOverrides });

const agent = agentName === "obscuro"
  ? new ChessObscuroAgent({ timeBudgetMs: budgetMs, particles: 4, rng: Math.random })
  : ChessAgent;

const lines = createInterface({ input: process.stdin });
const queued = [];
let waiter = null;
let closed = false;
lines.on("close", () => {
  closed = true;
  if (!waiter) return;
  const resolve = waiter;
  waiter = null;
  resolve("");
});
lines.on("line", line => {
  if (waiter) {
    const resolve = waiter;
    waiter = null;
    resolve(line);
    return;
  }
  queued.push(line);
});
function readLine() {
  if (queued.length) return Promise.resolve(queued.shift());
  return new Promise(resolve => { waiter = resolve; });
}

const rights = freshRights();
let side = "white";
let previous = null;
let turn = 1;

const greeting = (await readLine()).trim().toLowerCase();
if (greeting !== "fow") process.exit(0);
const header = (await readLine()).trim().split(/\s+/);
if (header.length !== 3 || !["w", "b"].includes(header[0].toLowerCase())) throw new Error("Expected color, base time, and increment");
side = header[0].toLowerCase() === "w" ? "white" : "black";
process.stdout.write("ready\n");

let observation = null;

for (;;) {
  const line = (await readLine()).trim();
  if (!line && closed) break;
  if (line.length === 64 && [...line].every(char => "?-PNBRQKpnbrqk".includes(char))) {
    observation = line;
    continue;
  }
  if (Number.isNaN(Number(line)) || !observation) continue;
  seeRights(rights, observation);
  const ep = inferEnPassant(previous, observation, side);
  previous = observation;
  const state = FogChess.createInitialState(
    [{ id: "white" }, { id: "black" }],
    { fogOfWar: true, board: boardFromView(observation), toMove: side, castlingRights: structuredClone(rights), enPassantTarget: ep, turnNumber: turn, difficulty },
  );
  state.viewerId = side;
  state.visibleSquares = [...observation].flatMap((char, index) => char === "?" ? [] : [squareName(index)]);
  const legal = FogChess.getLegalActions(state, side).filter(action => observationMove(observation, action));
  if (!legal.length) process.exit(0);
  const chosen = await agent.chooseAction(state, legal);
  const action = legal.find(item => item.from === chosen?.from && item.to === chosen?.to && item.payload?.promote === chosen?.payload?.promote) ?? legal[0];
  turn += 1;
  process.stdout.write(`move ${actionUci(action)}\n`);
}
