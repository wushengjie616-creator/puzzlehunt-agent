"""Human-style Sudoku singles engine. There is deliberately no search path."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any, Iterable

from .contracts import Assignment, SudokuError, SudokuSpec, SudokuState


Coordinate = tuple[int, int]


def _cell_name(cell: Coordinate) -> str:
    return f"R{cell[0] + 1}C{cell[1] + 1}"


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_regions(payload: dict[str, Any], size: int) -> tuple[tuple[Coordinate, ...], ...]:
    raw_regions = payload.get("regions")
    if raw_regions is not None:
        try:
            regions = tuple(tuple((int(cell[0]), int(cell[1])) for cell in region) for region in raw_regions)
        except (TypeError, ValueError, IndexError) as exc:
            raise SudokuError("regions must be coordinate lists") from exc
    else:
        box_rows = payload.get("box_rows")
        box_cols = payload.get("box_cols")
        if box_rows is None and box_cols is None and size == 9:
            box_rows = box_cols = 3
        if not isinstance(box_rows, int) or not isinstance(box_cols, int):
            raise SudokuError("non-9x9 Sudoku requires explicit regions or box_rows/box_cols")
        if box_rows <= 0 or box_cols <= 0 or box_rows * box_cols != size:
            raise SudokuError("box_rows * box_cols must equal size")
        if size % box_rows or size % box_cols:
            raise SudokuError("box shape must tile the grid")
        built: list[tuple[Coordinate, ...]] = []
        for top in range(0, size, box_rows):
            for left in range(0, size, box_cols):
                built.append(tuple(
                    (row, column)
                    for row in range(top, top + box_rows)
                    for column in range(left, left + box_cols)
                ))
        regions = tuple(built)

    expected = {(row, column) for row in range(size) for column in range(size)}
    flattened = [cell for region in regions for cell in region]
    if len(regions) != size or any(len(region) != size for region in regions):
        raise SudokuError("region partition must contain size regions of size cells")
    if set(flattened) != expected or len(flattened) != len(set(flattened)):
        raise SudokuError("regions must form an exact grid partition")
    return regions


def validate_spec(payload: dict[str, Any]) -> SudokuSpec:
    if not isinstance(payload, dict):
        raise SudokuError("Sudoku input must be an object")
    size = payload.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= 25:
        raise SudokuError("size must be an integer in 1..25")
    raw_symbols = payload.get("symbols", list(range(1, size + 1)))
    if (
        not isinstance(raw_symbols, list)
        or len(raw_symbols) != size
        or any(not isinstance(value, int) or isinstance(value, bool) for value in raw_symbols)
        or len(set(raw_symbols)) != size
    ):
        raise SudokuError("symbols must contain size unique integers")
    return SudokuSpec(size, tuple(raw_symbols), _parse_regions(payload, size))


def _unit_cells(spec: SudokuSpec, kind: str, index: int) -> tuple[Coordinate, ...]:
    if not 0 <= index < spec.size:
        raise SudokuError("unit index outside grid")
    if kind == "row":
        return tuple((index, column) for column in range(spec.size))
    if kind == "column":
        return tuple((row, index) for row in range(spec.size))
    if kind == "region":
        return spec.regions[index]
    raise SudokuError(f"unknown unit kind: {kind}")


def _all_units(spec: SudokuSpec) -> Iterable[tuple[str, int, tuple[Coordinate, ...]]]:
    for kind in ("row", "column", "region"):
        for index in range(spec.size):
            yield kind, index, _unit_cells(spec, kind, index)


def _validate_grid(spec: SudokuSpec, raw_grid: Any) -> list[list[int | None]]:
    if not isinstance(raw_grid, list) or len(raw_grid) != spec.size:
        raise SudokuError("grid must contain size rows")
    grid: list[list[int | None]] = []
    allowed = set(spec.symbols)
    for raw_row in raw_grid:
        if not isinstance(raw_row, list) or len(raw_row) != spec.size:
            raise SudokuError("every grid row must contain size cells")
        row: list[int | None] = []
        for value in raw_row:
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value not in allowed):
                raise SudokuError("grid values must be null or members of symbols")
            row.append(value)
        grid.append(row)
    for kind, index, cells in _all_units(spec):
        values = [grid[row][column] for row, column in cells if grid[row][column] is not None]
        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            raise SudokuError(f"duplicate value in {kind} {index + 1}: {duplicates[0]}")
    return grid


def _region_index(spec: SudokuSpec, cell: Coordinate) -> int:
    return next(index for index, region in enumerate(spec.regions) if cell in region)


def candidates_for_cell(state: SudokuState, row: int, column: int) -> frozenset[int]:
    if state.grid[row][column] is not None:
        return frozenset()
    used = {value for value in state.grid[row] if value is not None}
    used.update(state.grid[r][column] for r in range(state.spec.size) if state.grid[r][column] is not None)
    used.update(
        state.grid[r][c]
        for r, c in state.spec.regions[_region_index(state.spec, (row, column))]
        if state.grid[r][c] is not None
    )
    return frozenset(set(state.spec.symbols) - used)


def initialize_candidates(state: SudokuState) -> None:
    state.candidates = {
        (row, column): candidates_for_cell(state, row, column)
        for row in range(state.spec.size)
        for column in range(state.spec.size)
        if state.grid[row][column] is None
    }
    empty = [_cell_name(cell) for cell, values in state.candidates.items() if not values]
    if empty:
        raise SudokuError(f"contradiction: no candidates for {empty[0]}")


def build_state(payload: dict[str, Any]) -> SudokuState:
    spec = validate_spec(payload)
    state = SudokuState(spec, _validate_grid(spec, payload.get("grid")), {})
    initialize_candidates(state)
    return state


def _fingerprint(state: SudokuState) -> str:
    return _stable_hash({
        "grid": state.grid,
        "candidates": {
            _cell_name(cell): sorted(values)
            for cell, values in sorted(state.candidates.items())
        },
    })


def find_naked_singles(state: SudokuState) -> list[Assignment]:
    return [
        {
            "technique": "naked_single",
            "target": _cell_name(cell),
            "cell": cell,
            "value": next(iter(values)),
            "premises": {"target_candidates_before": sorted(values)},
        }
        for cell, values in sorted(state.candidates.items())
        if len(values) == 1
    ]


def find_hidden_singles_in_unit(state: SudokuState, kind: str, index: int) -> list[Assignment]:
    cells = _unit_cells(state.spec, kind, index)
    present = {state.grid[row][column] for row, column in cells if state.grid[row][column] is not None}
    found: list[Assignment] = []
    for symbol in state.spec.symbols:
        if symbol in present:
            continue
        positions = [cell for cell in cells if symbol in state.candidates.get(cell, ())]
        if not positions:
            raise SudokuError(f"contradiction: {symbol} has no candidate in {kind} {index + 1}")
        if len(positions) == 1:
            cell = positions[0]
            found.append({
                "technique": f"hidden_single_{kind}",
                "target": _cell_name(cell),
                "cell": cell,
                "value": symbol,
                "premises": {
                    "unit": f"{kind}:{index + 1}",
                    "missing_symbol": symbol,
                    "candidate_positions": [_cell_name(item) for item in positions],
                    "target_candidates_before": sorted(state.candidates[cell]),
                },
            })
    return found


def _next_assignment(state: SudokuState) -> Assignment | None:
    naked = find_naked_singles(state)
    if naked:
        return naked[0]
    for kind in ("row", "column", "region"):
        for index in range(state.spec.size):
            if all(state.grid[row][column] is not None for row, column in _unit_cells(state.spec, kind, index)):
                continue
            hidden = find_hidden_singles_in_unit(state, kind, index)
            if hidden:
                return hidden[0]
    return None


def _apply_assignment(state: SudokuState, assignment: Assignment, index: int) -> dict[str, Any]:
    row, column = assignment["cell"]
    value = assignment["value"]
    if value not in state.candidates.get((row, column), ()):
        raise SudokuError("assignment value is not a current candidate")
    before = _fingerprint(state)
    state.grid[row][column] = value
    initialize_candidates(state)
    after = _fingerprint(state)
    return {
        "index": index,
        "technique": assignment["technique"],
        "target": assignment["target"],
        "value": value,
        "premises": assignment["premises"],
        "before_fingerprint": before,
        "after_fingerprint": after,
    }


def _candidate_matrix(state: SudokuState) -> list[list[list[int]]]:
    return [
        [sorted(state.candidates.get((row, column), ())) for column in range(state.spec.size)]
        for row in range(state.spec.size)
    ]


def _is_solved(state: SudokuState) -> bool:
    if any(value is None for row in state.grid for value in row):
        return False
    expected = set(state.spec.symbols)
    return all(
        {state.grid[row][column] for row, column in cells} == expected
        for _, _, cells in _all_units(state.spec)
    )


def solve_sudoku(payload: dict[str, Any], *, max_steps: int | None = None) -> dict[str, Any]:
    state = build_state(payload)
    givens_hash = _stable_hash({"grid": state.grid, "regions": state.spec.regions, "symbols": state.spec.symbols})
    steps: list[dict[str, Any]] = []
    limit = max_steps if max_steps is not None else state.spec.size * state.spec.size
    while len(steps) < limit and not _is_solved(state):
        assignment = _next_assignment(state)
        if assignment is None:
            break
        steps.append(_apply_assignment(state, assignment, len(steps) + 1))
    status = "SOLVED" if _is_solved(state) else "STALLED"
    return {
        "status": status,
        "grid": [row[:] for row in state.grid],
        "candidates": _candidate_matrix(state),
        "steps": steps,
        "unresolved_cells": sum(value is None for row in state.grid for value in row),
        "givens_hash": givens_hash,
        "state_fingerprint": _fingerprint(state),
        "advisory": None if status == "SOLVED" else {
            "status": "UNVERIFIED_ADVISORY",
            "message": "Singles reached a fixed point; a verified higher-order technique is required.",
        },
    }


def replay_trace(payload: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    state = build_state(payload)
    for index, supplied in enumerate(steps, 1):
        expected = _next_assignment(state)
        if expected is None:
            raise SudokuError(f"replay failed at step {index}: no justified assignment")
        if supplied.get("before_fingerprint") != _fingerprint(state):
            raise SudokuError(f"replay failed at step {index}: before fingerprint mismatch")
        for key in ("technique", "target", "value", "premises"):
            if supplied.get(key) != expected.get(key):
                raise SudokuError(f"replay failed at step {index}: {key} mismatch")
        actual = _apply_assignment(state, expected, index)
        if supplied.get("after_fingerprint") != actual["after_fingerprint"]:
            raise SudokuError(f"replay failed at step {index}: after fingerprint mismatch")
    return {
        "status": "SOLVED" if _is_solved(state) else "STALLED",
        "grid": [row[:] for row in state.grid],
        "state_fingerprint": _fingerprint(state),
    }
