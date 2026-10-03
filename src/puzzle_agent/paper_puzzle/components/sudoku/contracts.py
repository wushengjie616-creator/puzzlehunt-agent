from dataclasses import dataclass
from typing import Any


class SudokuError(ValueError):
    """The Sudoku specification, state, or proof trace is invalid."""


@dataclass(frozen=True)
class SudokuSpec:
    size: int
    symbols: tuple[int, ...]
    regions: tuple[tuple[tuple[int, int], ...], ...]


@dataclass
class SudokuState:
    spec: SudokuSpec
    grid: list[list[int | None]]
    candidates: dict[tuple[int, int], frozenset[int]]


Assignment = dict[str, Any]
