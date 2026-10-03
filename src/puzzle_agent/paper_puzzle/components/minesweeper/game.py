"""Server-authoritative interactive Minesweeper with deterministic hints."""

from __future__ import annotations

from collections import OrderedDict, deque
import random
from threading import RLock
import time
from typing import Any
import uuid


DIFFICULTIES = {
    "beginner": (9, 9, 10),
    "intermediate": (16, 16, 40),
    "expert": (16, 30, 99),
}

Coordinate = tuple[int, int]


class MinesweeperError(ValueError):
    """Invalid Minesweeper configuration, coordinate, or action."""


class MinesweeperGame:
    def __init__(
        self, rows: int, columns: int, mine_count: int, *,
        rng: random.Random | None = None, difficulty: str | None = None,
    ):
        if (
            not isinstance(rows, int) or isinstance(rows, bool)
            or not isinstance(columns, int) or isinstance(columns, bool)
            or not 2 <= rows <= 30 or not 2 <= columns <= 40
        ):
            raise MinesweeperError("rows and columns must be bounded integers")
        if (
            not isinstance(mine_count, int) or isinstance(mine_count, bool)
            or not 1 <= mine_count < rows * columns
        ):
            raise MinesweeperError("mine count must leave at least one safe cell")
        self.rows = rows
        self.columns = columns
        self.mine_count = mine_count
        self.difficulty = difficulty
        self.status = "READY"
        self._rng = rng or random.SystemRandom()
        self._mines: set[Coordinate] = set()
        self._revealed: set[Coordinate] = set()
        self._flags: set[Coordinate] = set()
        self._exploded: Coordinate | None = None
        self._started_at: float | None = None
        self._ended_at: float | None = None
        self._lock = RLock()

    def neighbors(self, row: int, column: int) -> tuple[Coordinate, ...]:
        self._validate_coordinate(row, column)
        return tuple(
            (near_row, near_column)
            for near_row in range(max(0, row - 1), min(self.rows, row + 2))
            for near_column in range(max(0, column - 1), min(self.columns, column + 2))
            if (near_row, near_column) != (row, column)
        )

    def _validate_coordinate(self, row: int, column: int) -> None:
        if (
            not isinstance(row, int) or isinstance(row, bool)
            or not isinstance(column, int) or isinstance(column, bool)
            or not 0 <= row < self.rows or not 0 <= column < self.columns
        ):
            raise MinesweeperError("coordinate is outside the board")

    def _place_mines(self, excluded: Coordinate) -> None:
        available = [
            (row, column)
            for row in range(self.rows)
            for column in range(self.columns)
            if (row, column) != excluded
        ]
        self._mines = set(self._rng.sample(available, self.mine_count))

    def _adjacent_count(self, cell: Coordinate) -> int:
        return sum(neighbor in self._mines for neighbor in self.neighbors(*cell))

    def reveal(self, row: int, column: int, *, now: float | None = None) -> dict[str, Any]:
        with self._lock:
            self._validate_coordinate(row, column)
            timestamp = time.monotonic() if now is None else now
            if self.status in {"WON", "LOST"}:
                return self.public_state(now=timestamp)
            cell = (row, column)
            if cell in self._flags or cell in self._revealed:
                return self.public_state(now=timestamp)
            if self.status == "READY":
                self._place_mines(cell)
                self.status = "PLAYING"
                self._started_at = timestamp
            if cell in self._mines:
                self._exploded = cell
                self.status = "LOST"
                self._ended_at = timestamp
            else:
                self._flood_reveal(cell)
                self._check_win(timestamp)
            return self.public_state(now=timestamp)

    def _flood_reveal(self, start: Coordinate) -> None:
        queue = deque([start])
        queued = {start}
        while queue:
            cell = queue.popleft()
            if cell in self._revealed or cell in self._flags or cell in self._mines:
                continue
            self._revealed.add(cell)
            if self._adjacent_count(cell) != 0:
                continue
            for neighbor in self.neighbors(*cell):
                if neighbor not in queued and neighbor not in self._mines:
                    queued.add(neighbor)
                    queue.append(neighbor)

    def toggle_flag(self, row: int, column: int, *, now: float | None = None) -> dict[str, Any]:
        with self._lock:
            self._validate_coordinate(row, column)
            timestamp = time.monotonic() if now is None else now
            if self.status in {"WON", "LOST"}:
                return self.public_state(now=timestamp)
            cell = (row, column)
            if cell in self._revealed:
                raise MinesweeperError("a revealed cell cannot be flagged")
            if cell in self._flags:
                self._flags.remove(cell)
            else:
                if len(self._flags) >= self.mine_count:
                    raise MinesweeperError("flag limit reached")
                self._flags.add(cell)
            return self.public_state(now=timestamp)

    def chord(self, row: int, column: int, *, now: float | None = None) -> dict[str, Any]:
        with self._lock:
            self._validate_coordinate(row, column)
            timestamp = time.monotonic() if now is None else now
            if self.status in {"WON", "LOST"}:
                return self.public_state(now=timestamp)
            cell = (row, column)
            if cell not in self._revealed:
                return self.public_state(now=timestamp)
            adjacent = self.neighbors(row, column)
            if sum(neighbor in self._flags for neighbor in adjacent) != self._adjacent_count(cell):
                return self.public_state(now=timestamp)
            for near_row, near_column in adjacent:
                near = (near_row, near_column)
                if near not in self._flags and near not in self._revealed:
                    self.reveal(near_row, near_column, now=timestamp)
                    if self.status == "LOST":
                        break
            return self.public_state(now=timestamp)

    def _check_win(self, timestamp: float) -> None:
        if len(self._revealed) == self.rows * self.columns - self.mine_count:
            self.status = "WON"
            self._ended_at = timestamp

    def _elapsed(self, now: float) -> int:
        if self._started_at is None:
            return 0
        end = self._ended_at if self._ended_at is not None else now
        return max(0, int(end - self._started_at))

    def public_state(self, *, now: float | None = None) -> dict[str, Any]:
        with self._lock:
            timestamp = time.monotonic() if now is None else now
            terminal = self.status in {"WON", "LOST"}
            board: list[list[dict[str, Any]]] = []
            for row in range(self.rows):
                public_row: list[dict[str, Any]] = []
                for column in range(self.columns):
                    cell = (row, column)
                    if cell == self._exploded:
                        item = {"state": "exploded"}
                    elif cell in self._revealed:
                        item = {"state": "revealed", "value": self._adjacent_count(cell)}
                    elif terminal and cell in self._mines:
                        item = {"state": "mine"}
                    elif cell in self._flags:
                        item = {"state": "flagged"}
                    else:
                        item = {"state": "covered"}
                    public_row.append(item)
                board.append(public_row)
            return {
                "status": self.status,
                "difficulty": self.difficulty,
                "rows": self.rows,
                "columns": self.columns,
                "mine_count": self.mine_count,
                "flags": len(self._flags),
                "remaining_mines": self.mine_count - len(self._flags),
                "revealed_count": len(self._revealed),
                "elapsed_seconds": self._elapsed(timestamp),
                "board": board,
            }

    def logical_hint(self, *, now: float | None = None) -> dict[str, Any]:
        """Return one proof-backed move using only the public clue surface."""
        with self._lock:
            if self.status in {"WON", "LOST"}:
                return {"status": "STALLED", "reason": "game is finished"}
            covered = {
                (row, column)
                for row in range(self.rows)
                for column in range(self.columns)
                if (row, column) not in self._revealed
            }
            known_mines: set[Coordinate] = set()
            known_safe: set[Coordinate] = set()
            mine_proof: dict[Coordinate, dict[str, Any]] = {}
            safe_proof: dict[Coordinate, dict[str, Any]] = {}
            changed = True
            while changed:
                changed = False
                for clue_cell in sorted(self._revealed):
                    clue = self._adjacent_count(clue_cell)
                    adjacent = set(self.neighbors(*clue_cell))
                    undecided = adjacent & covered - known_mines - known_safe
                    remaining = clue - len(adjacent & known_mines)
                    premise = {
                        "clue": [clue_cell[0], clue_cell[1]],
                        "value": clue,
                        "known_mines": len(adjacent & known_mines),
                        "undecided": [list(cell) for cell in sorted(undecided)],
                    }
                    if remaining == 0 and undecided:
                        for candidate in undecided:
                            if candidate not in known_safe:
                                known_safe.add(candidate)
                                safe_proof[candidate] = premise
                                changed = True
                    elif remaining == len(undecided) and remaining > 0:
                        for candidate in undecided:
                            if candidate not in known_mines:
                                known_mines.add(candidate)
                                mine_proof[candidate] = premise
                                changed = True
            if known_mines:
                cell = min(known_mines)
                return {
                    "status": "DEDUCED", "kind": "mine", "cell": list(cell),
                    "premise": mine_proof[cell],
                    "message": f"R{cell[0] + 1}C{cell[1] + 1} 必为雷。",
                }
            if known_safe:
                cell = min(known_safe)
                return {
                    "status": "DEDUCED", "kind": "safe", "cell": list(cell),
                    "premise": safe_proof[cell],
                    "message": f"R{cell[0] + 1}C{cell[1] + 1} 可以安全翻开。",
                }
            return {"status": "STALLED", "reason": "当前公开数字不能推出唯一安全格或雷格"}


class MinesweeperStore:
    def __init__(self, *, max_games: int = 64):
        if not isinstance(max_games, int) or not 1 <= max_games <= 1024:
            raise MinesweeperError("max_games must be in 1..1024")
        self.max_games = max_games
        self._games: OrderedDict[str, MinesweeperGame] = OrderedDict()
        self._lock = RLock()

    def create(self, difficulty: str) -> tuple[str, MinesweeperGame]:
        if difficulty not in DIFFICULTIES:
            raise MinesweeperError("unknown difficulty")
        with self._lock:
            while len(self._games) >= self.max_games:
                self._games.popitem(last=False)
            game_id = uuid.uuid4().hex
            game = MinesweeperGame(*DIFFICULTIES[difficulty], difficulty=difficulty)
            self._games[game_id] = game
            return game_id, game

    def get(self, game_id: str) -> MinesweeperGame:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise MinesweeperError("Unknown Minesweeper game")
            return game
