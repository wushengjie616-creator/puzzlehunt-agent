"""Deterministic Nonogram line propagation. There is deliberately no search path."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from typing import Any, Sequence

from .contracts import Cell, NonogramError, NonogramSpec, NonogramState


MAX_LINES = 50
MAX_CELLS = 2_500
MAX_LINE_PATTERNS = 100_000


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_clues(raw: Any, *, line_length: int, name: str) -> tuple[tuple[int, ...], ...]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_LINES:
        raise NonogramError(f"{name} must contain 1..{MAX_LINES} clue lists")
    parsed: list[tuple[int, ...]] = []
    for index, raw_clue in enumerate(raw):
        if not isinstance(raw_clue, list):
            raise NonogramError(f"{name} {index + 1} must be a list")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in raw_clue
        ):
            raise NonogramError("clues must contain positive integers; use [] for an empty line")
        clue = tuple(raw_clue)
        minimum = sum(clue) + max(0, len(clue) - 1)
        if minimum > line_length:
            raise NonogramError(f"{name} {index + 1} does not fit line length {line_length}")
        parsed.append(clue)
    return tuple(parsed)


def validate_spec(payload: dict[str, Any]) -> NonogramSpec:
    if not isinstance(payload, dict):
        raise NonogramError("Nonogram input must be an object")
    raw_rows = payload.get("row_clues")
    raw_columns = payload.get("column_clues")
    if not isinstance(raw_rows, list) or not isinstance(raw_columns, list):
        raise NonogramError("row_clues and column_clues must be arrays")
    rows = len(raw_rows)
    columns = len(raw_columns)
    if not 1 <= rows <= MAX_LINES or not 1 <= columns <= MAX_LINES:
        raise NonogramError(f"row and column counts must be in 1..{MAX_LINES}")
    if rows * columns > MAX_CELLS:
        raise NonogramError(f"Nonogram grid must contain at most {MAX_CELLS} cells")
    return NonogramSpec(
        _parse_clues(raw_rows, line_length=columns, name="row_clues"),
        _parse_clues(raw_columns, line_length=rows, name="column_clues"),
    )


def build_state(payload: dict[str, Any]) -> NonogramState:
    spec = validate_spec(payload)
    raw_grid = payload.get("grid")
    if raw_grid is None:
        grid = [[None] * spec.columns for _ in range(spec.rows)]
    else:
        if not isinstance(raw_grid, list) or len(raw_grid) != spec.rows:
            raise NonogramError("grid must match the number of row clues")
        grid: list[list[Cell]] = []
        for raw_row in raw_grid:
            if not isinstance(raw_row, list) or len(raw_row) != spec.columns:
                raise NonogramError("every grid row must match the number of column clues")
            if any(
                cell is not None
                and (not isinstance(cell, int) or isinstance(cell, bool) or cell not in {0, 1})
                for cell in raw_row
            ):
                raise NonogramError("grid cells must be null, 0 (empty), or 1 (filled)")
            grid.append(list(raw_row))
    return NonogramState(spec, grid)


@lru_cache(maxsize=512)
def _generate_cached(
    length: int, clues: tuple[int, ...], max_patterns: int,
) -> tuple[tuple[int, ...], ...]:
    patterns: list[tuple[int, ...]] = []
    starts: list[int] = []

    def place(block_index: int, minimum_start: int) -> None:
        if block_index == len(clues):
            pattern = [0] * length
            for start, block_length in zip(starts, clues):
                pattern[start:start + block_length] = [1] * block_length
            patterns.append(tuple(pattern))
            if len(patterns) > max_patterns:
                raise NonogramError(f"line pattern limit exceeded ({max_patterns})")
            return
        remaining = clues[block_index:]
        required = sum(remaining) + len(remaining) - 1
        max_start = length - required
        for start in range(minimum_start, max_start + 1):
            starts.append(start)
            place(block_index + 1, start + clues[block_index] + 1)
            starts.pop()

    place(0, 0)
    return tuple(patterns)


def generate_line_patterns(
    length: int, clues: Sequence[int], *, max_patterns: int = MAX_LINE_PATTERNS,
) -> tuple[tuple[int, ...], ...]:
    if not isinstance(length, int) or isinstance(length, bool) or not 1 <= length <= MAX_LINES:
        raise NonogramError(f"line length must be in 1..{MAX_LINES}")
    if not isinstance(max_patterns, int) or isinstance(max_patterns, bool) or max_patterns < 1:
        raise NonogramError("max_patterns must be a positive integer")
    clue_tuple = tuple(clues)
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in clue_tuple
    ):
        raise NonogramError("clues must contain positive integers")
    if sum(clue_tuple) + max(0, len(clue_tuple) - 1) > length:
        raise NonogramError("clues do not fit line length")
    return _generate_cached(length, clue_tuple, max_patterns)


def filter_compatible_patterns(
    patterns: Sequence[Sequence[int]], known_line: Sequence[Cell],
) -> tuple[tuple[int, ...], ...]:
    known = tuple(known_line)
    if any(value not in {None, 0, 1} or isinstance(value, bool) for value in known):
        raise NonogramError("known line cells must be null, 0, or 1")
    normalized: list[tuple[int, ...]] = []
    for pattern in patterns:
        item = tuple(pattern)
        if len(item) != len(known) or any(value not in {0, 1} for value in item):
            raise NonogramError("line patterns must be equally sized binary sequences")
        if all(current is None or current == proposed for current, proposed in zip(known, item)):
            normalized.append(item)
    return tuple(normalized)


def intersect_patterns(patterns: Sequence[Sequence[int]]) -> tuple[Cell, ...]:
    normalized = tuple(tuple(pattern) for pattern in patterns)
    if not normalized:
        raise NonogramError("contradiction: line has no compatible patterns")
    length = len(normalized[0])
    if any(len(pattern) != length for pattern in normalized):
        raise NonogramError("line patterns must have equal lengths")
    return tuple(
        normalized[0][index]
        if all(pattern[index] == normalized[0][index] for pattern in normalized[1:])
        else None
        for index in range(length)
    )


def _line(state: NonogramState, kind: str, index: int) -> tuple[list[Cell], tuple[int, ...]]:
    if kind == "row" and 0 <= index < state.spec.rows:
        return list(state.grid[index]), state.spec.row_clues[index]
    if kind == "column" and 0 <= index < state.spec.columns:
        return [state.grid[row][index] for row in range(state.spec.rows)], state.spec.column_clues[index]
    raise NonogramError("line kind or index is outside the grid")


def _coordinate(kind: str, index: int, offset: int) -> tuple[int, int]:
    return (index, offset) if kind == "row" else (offset, index)


def _cell_name(row: int, column: int) -> str:
    return f"R{row + 1}C{column + 1}"


def _fingerprint(state: NonogramState) -> str:
    return _stable_hash({
        "row_clues": state.spec.row_clues,
        "column_clues": state.spec.column_clues,
        "grid": state.grid,
    })


def _runs(line: Sequence[Cell]) -> tuple[int, ...]:
    runs: list[int] = []
    current = 0
    for cell in line:
        if cell == 1:
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return tuple(runs)


def _line_is_complete(state: NonogramState, kind: str, index: int) -> bool:
    line, clues = _line(state, kind, index)
    return None not in line and _runs(line) == clues


def analyze_line(state: NonogramState, kind: str, index: int) -> dict[str, Any]:
    known, clues = _line(state, kind, index)
    patterns = generate_line_patterns(len(known), clues)
    compatible = filter_compatible_patterns(patterns, known)
    if not compatible:
        raise NonogramError(f"contradiction: {kind} {index + 1} has no compatible patterns")
    common = intersect_patterns(compatible)
    deductions = []
    common_filled = []
    common_empty = []
    for offset, state_value in enumerate(common):
        row, column = _coordinate(kind, index, offset)
        if state_value == 1:
            common_filled.append(_cell_name(row, column))
        elif state_value == 0:
            common_empty.append(_cell_name(row, column))
        if known[offset] is None and state_value is not None:
            deductions.append({"cell": [row, column], "state": state_value})
    return {
        "kind": kind,
        "index": index,
        "label": f"{'R' if kind == 'row' else 'C'}{index + 1}",
        "clues": list(clues),
        "complete": _line_is_complete(state, kind, index),
        "compatible_pattern_count": len(compatible),
        "common_filled": common_filled,
        "common_empty": common_empty,
        "deductions": deductions,
    }


def apply_line_deductions(
    state: NonogramState, analysis: dict[str, Any], step_index: int,
) -> dict[str, Any]:
    if not isinstance(step_index, int) or step_index < 1:
        raise NonogramError("step index must be positive")
    kind, index = analysis.get("kind"), analysis.get("index")
    expected = analyze_line(state, kind, index)
    if analysis != expected:
        raise NonogramError("line analysis is stale or invalid")
    if not expected["deductions"]:
        raise NonogramError("line analysis has no new deductions")
    before = _fingerprint(state)
    changes = []
    for deduction in expected["deductions"]:
        row, column = deduction["cell"]
        value = deduction["state"]
        if state.grid[row][column] is not None and state.grid[row][column] != value:
            raise NonogramError("contradiction: deduction conflicts with known cell")
        if state.grid[row][column] is None:
            state.grid[row][column] = value
            changes.append({
                "cell": [row, column],
                "target": _cell_name(row, column),
                "state": value,
            })
    return {
        "index": step_index,
        "technique": "line_intersection",
        "unit": {"kind": kind, "index": index, "label": expected["label"]},
        "clues": expected["clues"],
        "premises": {
            "compatible_pattern_count": expected["compatible_pattern_count"],
            "common_filled": expected["common_filled"],
            "common_empty": expected["common_empty"],
        },
        "changes": changes,
        "before_fingerprint": before,
        "after_fingerprint": _fingerprint(state),
    }


def is_solved(state: NonogramState) -> bool:
    if any(cell is None for row in state.grid for cell in row):
        return False
    return all(
        _line_is_complete(state, "row", index) for index in range(state.spec.rows)
    ) and all(
        _line_is_complete(state, "column", index) for index in range(state.spec.columns)
    )


def _next_analysis(state: NonogramState) -> dict[str, Any] | None:
    for kind, count in (("row", state.spec.rows), ("column", state.spec.columns)):
        for index in range(count):
            if _line_is_complete(state, kind, index):
                continue
            analysis = analyze_line(state, kind, index)
            if analysis["deductions"]:
                return analysis
    return None


def _result(state: NonogramState, steps: list[dict[str, Any]]) -> dict[str, Any]:
    status = "SOLVED" if is_solved(state) else "STALLED"
    return {
        "status": status,
        "grid": [row[:] for row in state.grid],
        "row_clues": [list(clue) for clue in state.spec.row_clues],
        "column_clues": [list(clue) for clue in state.spec.column_clues],
        "steps": steps,
        "unresolved_cells": sum(cell is None for row in state.grid for cell in row),
        "state_fingerprint": _fingerprint(state),
        "advisory": None if status == "SOLVED" else {
            "status": "UNVERIFIED_ADVISORY",
            "message": "Line intersection reached a fixed point; a verified higher-order deduction is required.",
        },
    }


def solve_nonogram(payload: dict[str, Any], *, max_steps: int | None = None) -> dict[str, Any]:
    state = build_state(payload)
    if max_steps is not None and (
        not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 0
    ):
        raise NonogramError("max_steps must be a non-negative integer")
    limit = state.spec.rows * state.spec.columns if max_steps is None else max_steps
    steps: list[dict[str, Any]] = []
    while len(steps) < limit and not is_solved(state):
        analysis = _next_analysis(state)
        if analysis is None:
            break
        steps.append(apply_line_deductions(state, analysis, len(steps) + 1))
    if not is_solved(state):
        for kind, count in (("row", state.spec.rows), ("column", state.spec.columns)):
            for index in range(count):
                analyze_line(state, kind, index)
    return _result(state, steps)


def replay_trace(payload: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(steps, list):
        raise NonogramError("replay steps must be a list")
    state = build_state(payload)
    verified: list[dict[str, Any]] = []
    for index, supplied in enumerate(steps, 1):
        analysis = _next_analysis(state)
        if analysis is None:
            raise NonogramError(f"replay failed at step {index}: no justified deduction")
        actual = apply_line_deductions(state, analysis, index)
        if supplied != actual:
            raise NonogramError(f"replay failed at step {index}: step mismatch")
        verified.append(actual)
    return _result(state, verified)
