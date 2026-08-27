"""Framework-neutral deterministic tools for complex puzzles."""

from collections import Counter
from dataclasses import dataclass
from itertools import permutations
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


def caesar_shift(text: str, shift: int) -> str:
    if not isinstance(text, str) or not isinstance(shift, int) or not -25 <= shift <= 25:
        raise ValueError("text must be a string and shift must be between -25 and 25")
    output: list[str] = []
    for character in text:
        if "A" <= character <= "Z":
            output.append(chr((ord(character) - ord("A") + shift) % 26 + ord("A")))
        elif "a" <= character <= "z":
            output.append(chr((ord(character) - ord("a") + shift) % 26 + ord("a")))
        else:
            output.append(character)
    return "".join(output)


def a1z26_decode(values: list[int]) -> str:
    if not isinstance(values, list) or not values:
        raise ValueError("values must be a non-empty list")
    if any(not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 26 for value in values):
        raise ValueError("A1Z26 values must be integers in 1..26")
    return "".join(chr(ord("A") + value - 1) for value in values)


def interleave_sequences(sequences: list[str]) -> str:
    if not isinstance(sequences, list) or len(sequences) < 2 or not all(
        isinstance(sequence, str) for sequence in sequences
    ):
        raise ValueError("sequences must contain at least two strings")
    lengths = {len(sequence) for sequence in sequences}
    if len(lengths) != 1:
        raise ValueError("sequences must have equal length")
    return "".join(sequence[index] for index in range(len(sequences[0])) for sequence in sequences)


def grid_trace(grid: list[str], start: list[int], directions: list[str]) -> dict[str, Any]:
    if not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must contain non-empty string rows")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid rows must have equal width")
    if not isinstance(start, list) or len(start) != 2 or not all(isinstance(v, int) for v in start):
        raise ValueError("start must be [row, column]")
    moves = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}
    if not isinstance(directions, list) or any(direction not in moves for direction in directions):
        raise ValueError("directions must use N, E, S, or W")
    row, column = start
    if not (0 <= row < len(grid) and 0 <= column < width):
        raise ValueError("start is outside grid")
    path = [[row, column]]
    output: list[str] = []
    for direction in directions:
        delta_row, delta_column = moves[direction]
        row += delta_row
        column += delta_column
        if not (0 <= row < len(grid) and 0 <= column < width):
            raise ValueError("direction path moves outside grid")
        path.append([row, column])
        output.append(grid[row][column])
    return {"output": "".join(output), "path": path}


def constrained_order(items: list[str], constraints: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(items, list) or not 1 <= len(items) <= 9 or len(set(items)) != len(items):
        raise ValueError("items must contain 1..9 unique values")
    if not isinstance(constraints, list) or not all(isinstance(item, dict) for item in constraints):
        raise ValueError("constraints must be a list of objects")
    item_set = set(items)

    def satisfies(order: tuple[str, ...]) -> bool:
        positions = {item: index for index, item in enumerate(order)}
        for constraint in constraints:
            kind = constraint.get("type")
            if kind in {"before", "immediately_before"}:
                left, right = constraint.get("left"), constraint.get("right")
                if left not in item_set or right not in item_set:
                    raise ValueError("constraint references an unknown item")
                difference = positions[right] - positions[left]
                if kind == "before" and difference <= 0:
                    return False
                if kind == "immediately_before" and difference != 1:
                    return False
            elif kind in {"start", "end"}:
                item = constraint.get("item")
                if item not in item_set:
                    raise ValueError("constraint references an unknown item")
                if kind == "start" and positions[item] != 0:
                    return False
                if kind == "end" and positions[item] != len(order) - 1:
                    return False
            else:
                raise ValueError(f"unknown constraint type: {kind}")
        return True

    solutions: list[list[str]] = []
    for order in permutations(items):
        if satisfies(order):
            solutions.append(list(order))
            if len(solutions) == 2:
                break
    status = "UNSAT" if not solutions else "SAT" if len(solutions) == 1 else "AMBIGUOUS"
    return {
        "status": status,
        "solutions": solutions,
        "solution_count": len(solutions),
        "truncated": len(solutions) == 2,
    }


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
                ToolSpec("caesar_shift", caesar_shift),
                ToolSpec("a1z26_decode", a1z26_decode),
                ToolSpec("interleave_sequences", interleave_sequences),
                ToolSpec("grid_trace", grid_trace),
                ToolSpec("constrained_order", constrained_order),
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
        output = spec.function(**arguments)
        if isinstance(output, dict) and "output" in output:
            return output
        return {"output": output}
