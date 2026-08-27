"""Framework-neutral deterministic tools for complex puzzles."""

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable


def extract_nth(lines: list[str], indices: list[int]) -> str:
    if len(lines) != len(indices):
        raise ValueError("lines and indices must have equal length")
    output: list[str] = []
    for line, index in zip(lines, indices):
        if not isinstance(line, str) or not isinstance(index, int) or index < 1 or index > len(line):
            raise ValueError("index is outside its source line")
        output.append(line[index - 1])
    return "".join(output)


def anagram_delta(source: str, removed: str) -> str:
    available = Counter(source.casefold())
    requested = Counter(removed.casefold())
    if requested - available:
        raise ValueError("removed text is not a multiset subset of source")
    remaining_to_remove = requested.copy()
    output: list[str] = []
    for character in source:
        folded = character.casefold()
        if remaining_to_remove[folded]:
            remaining_to_remove[folded] -= 1
        else:
            output.append(character)
    return "".join(output)


def read_grid_path(grid: list[str], path: list[list[int]]) -> str:
    if not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must contain non-empty string rows")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid rows must have equal width")
    output: list[str] = []
    previous: tuple[int, int] | None = None
    for coordinate in path:
        if (
            not isinstance(coordinate, list)
            or len(coordinate) != 2
            or not all(isinstance(value, int) for value in coordinate)
        ):
            raise ValueError("path coordinates must be [row, column]")
        row, column = coordinate
        if not (0 <= row < len(grid) and 0 <= column < width):
            raise ValueError("path coordinate is outside grid")
        if previous is not None and abs(row - previous[0]) + abs(column - previous[1]) != 1:
            raise ValueError("path coordinates must be orthogonally adjacent")
        output.append(grid[row][column])
        previous = row, column
    return "".join(output)


def dependency_order(dependencies: dict[str, list[str]]) -> list[str]:
    nodes = set(dependencies)
    referenced = {item for values in dependencies.values() for item in values}
    unknown = referenced - nodes
    if unknown:
        raise ValueError(f"unknown dependencies: {sorted(unknown)}")
    remaining = {node: set(values) for node, values in dependencies.items()}
    result: list[str] = []
    while remaining:
        ready = sorted(node for node, values in remaining.items() if not values)
        if not ready:
            raise ValueError("dependency cycle detected")
        for node in ready:
            result.append(node)
            del remaining[node]
        for values in remaining.values():
            values.difference_update(ready)
    return result


@dataclass(frozen=True)
class ToolSpec:
    name: str
    function: Callable[..., Any]
    deterministic: bool = True


class ToolRegistry:
    def __init__(self):
        self._specs = {
            spec.name: spec for spec in (
                ToolSpec("extract_nth", extract_nth),
                ToolSpec("anagram_delta", anagram_delta),
                ToolSpec("read_grid_path", read_grid_path),
                ToolSpec("dependency_order", dependency_order),
            )
        }

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        spec = self._specs.get(name)
        if spec is None:
            raise ValueError(f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be a JSON object")
        return {"output": spec.function(**arguments)}
