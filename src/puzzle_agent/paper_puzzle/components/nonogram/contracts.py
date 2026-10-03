from dataclasses import dataclass


class NonogramError(ValueError):
    """The Nonogram specification, state, or proof trace is invalid."""


Cell = int | None
Clues = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class NonogramSpec:
    row_clues: Clues
    column_clues: Clues

    @property
    def rows(self) -> int:
        return len(self.row_clues)

    @property
    def columns(self) -> int:
        return len(self.column_clues)


@dataclass
class NonogramState:
    spec: NonogramSpec
    grid: list[list[Cell]]
