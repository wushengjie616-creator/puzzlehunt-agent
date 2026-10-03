"""Framework-neutral deterministic tools for complex puzzles."""

from collections import Counter
from dataclasses import dataclass
from itertools import permutations
import inspect
from typing import Any, Callable
import unicodedata

from .cipher_workbench import (
    atbash,
    decode_base,
    decode_morse,
    rail_fence_decode as _rail_fence_decode,
    vigenere_decode as _vigenere_decode,
)
from .cipher_reference import lookup_cipher_reference


_MAX_TOOL_TEXT = 10_000


def _bounded_text(text: str) -> str:
    if not isinstance(text, str) or not text or len(text) > _MAX_TOOL_TEXT:
        raise ValueError(f"text must be a non-empty string bounded to {_MAX_TOOL_TEXT} characters")
    return text


def atbash_transform(text: str) -> str:
    return atbash(_bounded_text(text))


def base_decode(text: str, base: int) -> str:
    _bounded_text(text)
    if not isinstance(base, int) or isinstance(base, bool) or base not in {16, 32, 64}:
        raise ValueError("base must be 16, 32, or 64")
    output = decode_base(text, base)
    if output is None:
        raise ValueError(f"text is not valid Base{base} UTF-8 data")
    return output


def morse_decode(text: str) -> str:
    output = decode_morse(_bounded_text(text))
    if output is None:
        raise ValueError("text is not valid dot/dash Morse")
    return output


def vigenere_decode(text: str, key: str) -> str:
    _bounded_text(text)
    if not isinstance(key, str) or not key or len(key) > 256:
        raise ValueError("key must be an explicit non-empty string bounded to 256 characters")
    return _vigenere_decode(text, key)


def rail_fence_decode(text: str, rails: int) -> str:
    _bounded_text(text)
    if not isinstance(rails, int) or isinstance(rails, bool) or rails < 2 or rails > 100:
        raise ValueError("rails must be an explicit integer in 2..100")
    return _rail_fence_decode(text, rails)


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


def decode_bit_patterns(patterns: list[str], *, bit_order: str = "msb") -> dict[str, Any]:
    if not isinstance(patterns, list) or not patterns or not all(isinstance(item, str) for item in patterns):
        raise ValueError("patterns must be a non-empty list of bit strings")
    widths = {len(item) for item in patterns}
    if len(widths) != 1:
        raise ValueError("bit patterns must have equal width")
    if not 1 <= next(iter(widths)) <= 8 or any(set(item) - {"0", "1"} for item in patterns):
        raise ValueError("bit patterns must contain 1..8 binary digits")
    if bit_order not in {"msb", "lsb"}:
        raise ValueError("bit_order must be msb or lsb")
    items: list[dict[str, Any]] = []
    output: list[str] = []
    for bits in patterns:
        effective = bits if bit_order == "msb" else bits[::-1]
        value = int(effective, 2)
        if not 1 <= value <= 26:
            raise ValueError("A1Z26 bit value must be in 1..26")
        symbol = chr(ord("A") + value - 1)
        items.append({"bits": bits, "value": value, "symbol": symbol})
        output.append(symbol)
    return {"output": "".join(output), "items": items, "bit_order": bit_order}


def repair_mojibake(text: str, *, current_codec: str, original_codec: str) -> dict[str, Any]:
    allowlist = {"utf-8", "gb18030", "big5", "shift_jis", "cp437", "latin-1"}
    if current_codec not in allowlist or original_codec not in allowlist:
        raise ValueError("codec must come from the bounded allowlist")
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("text must be a bounded string")
    try:
        output = text.encode(current_codec, errors="strict").decode(original_codec, errors="strict")
        round_trip = output.encode(original_codec, errors="strict").decode(
            current_codec, errors="strict"
        ) == text
    except UnicodeError as exc:
        raise ValueError("codec chain is not strictly reversible") from exc
    if not round_trip:
        raise ValueError("codec chain failed strict round trip")
    return {
        "output": output,
        "path": [f"encode:{current_codec}", f"decode:{original_codec}"],
        "round_trip": True,
    }


_MOJIBAKE_REPAIR_PAIRS = (
    ("latin-1", "utf-8"),
    ("cp1252", "utf-8"),
    ("gb18030", "utf-8"),
    ("big5", "utf-8"),
    ("shift_jis", "utf-8"),
    ("latin-1", "gb18030"),
    ("latin-1", "big5"),
    ("latin-1", "shift_jis"),
)
_MAX_MOJIBAKE_SCAN_TEXT = 4_096
_MAX_MOJIBAKE_CANDIDATES = 32


def bounded_mojibake_scan(text: str, *, max_depth: int = 2) -> dict[str, Any]:
    if not isinstance(text, str) or not text:
        raise ValueError("text must be an explicit non-empty string")
    if len(text) > _MAX_MOJIBAKE_SCAN_TEXT:
        raise ValueError(f"text must be bounded to {_MAX_MOJIBAKE_SCAN_TEXT} characters")
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth not in {1, 2}:
        raise ValueError("max_depth must be 1 or 2")

    candidates: list[dict[str, Any]] = []
    seen = {text}
    frontier = [(text, [])]
    attempted_paths = 0
    truncated = False
    for _ in range(max_depth):
        next_frontier: list[tuple[str, list[str]]] = []
        for current, current_path in frontier:
            for encoded_as, decoded_as in _MOJIBAKE_REPAIR_PAIRS:
                attempted_paths += 1
                try:
                    repaired = current.encode(encoded_as, errors="strict").decode(
                        decoded_as, errors="strict"
                    )
                    reversible = repaired.encode(decoded_as, errors="strict").decode(
                        encoded_as, errors="strict"
                    ) == current
                except UnicodeError:
                    continue
                if not reversible or repaired in seen:
                    continue
                seen.add(repaired)
                path = current_path + [f"encode:{encoded_as}", f"decode:{decoded_as}"]
                candidates.append({"text": repaired, "path": path, "round_trip": True})
                next_frontier.append((repaired, path))
                if len(candidates) == _MAX_MOJIBAKE_CANDIDATES:
                    truncated = True
                    break
            if truncated:
                break
        if truncated or not next_frontier:
            break
        frontier = next_frontier
    return {
        "output": candidates,
        "candidates": candidates,
        "attempted_paths": attempted_paths,
        "max_depth": max_depth,
        "truncated": truncated,
        "scored": False,
    }


def common_symbol_intersection(
    values: list[str], *, exactly_one: bool = False, normalization: str = "none"
) -> dict[str, Any]:
    import unicodedata

    if not isinstance(values, list) or len(values) < 2 or not all(isinstance(item, str) for item in values):
        raise ValueError("values must contain at least two strings")
    if normalization not in {"none", "NFC", "NFKC"}:
        raise ValueError("normalization must be none, NFC, or NFKC")
    normalized = values if normalization == "none" else [
        unicodedata.normalize(normalization, item) for item in values
    ]
    common = set(normalized[0]).intersection(*(set(item) for item in normalized[1:]))
    if exactly_one and len(common) != 1:
        raise ValueError("expected exactly one common symbol")
    symbols = sorted(common)
    positions = {
        symbol: [[index + 1 for index, character in enumerate(item) if character == symbol]
                 for item in normalized]
        for symbol in symbols
    }
    return {"output": "".join(symbols), "positions": positions, "normalization": normalization}


def grid_transform(grid: list[str], *, operation: str) -> dict[str, Any]:
    if not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must be a non-empty rectangular string grid")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid must be rectangular")
    matrix = [list(row) for row in grid]
    if operation == "transpose":
        transformed = [list(row) for row in zip(*matrix)]
    elif operation == "rotate90":
        transformed = [list(row) for row in zip(*matrix[::-1])]
    elif operation == "rotate180":
        transformed = [row[::-1] for row in matrix[::-1]]
    elif operation == "rotate270":
        transformed = [list(row) for row in zip(*matrix)][::-1]
    elif operation == "flip_h":
        transformed = [row[::-1] for row in matrix]
    elif operation == "flip_v":
        transformed = matrix[::-1]
    else:
        raise ValueError("unknown grid transform operation")
    return {"output": ["".join(row) for row in transformed], "operation": operation}


def phone_keypad_decode(groups: list[str]) -> str:
    mapping = {
        "2": "ABC", "3": "DEF", "4": "GHI", "5": "JKL",
        "6": "MNO", "7": "PQRS", "8": "TUV", "9": "WXYZ",
    }
    if not isinstance(groups, list) or not groups:
        raise ValueError("multitap groups must be a non-empty list")
    output: list[str] = []
    for group in groups:
        if not isinstance(group, str) or not group or len(set(group)) != 1:
            raise ValueError("each multitap group must repeat one digit")
        letters = mapping.get(group[0])
        if letters is None or len(group) > len(letters):
            raise ValueError("invalid multitap group")
        output.append(letters[len(group) - 1])
    return "".join(output)


_BRAILLE = {
    frozenset(dots): chr(ord("A") + index)
    for index, dots in enumerate((
        (1,), (1, 2), (1, 4), (1, 4, 5), (1, 5), (1, 2, 4), (1, 2, 4, 5),
        (1, 2, 5), (2, 4), (2, 4, 5), (1, 3), (1, 2, 3), (1, 3, 4),
        (1, 3, 4, 5), (1, 3, 5), (1, 2, 3, 4), (1, 2, 3, 4, 5),
        (1, 2, 3, 5), (2, 3, 4), (2, 3, 4, 5), (1, 3, 6), (1, 2, 3, 6),
        (2, 4, 5, 6), (1, 3, 4, 6), (1, 3, 4, 5, 6), (1, 3, 5, 6),
    ))
}


def braille_decode(cells: list[list[int]]) -> str:
    if not isinstance(cells, list) or not cells:
        raise ValueError("cells must be a non-empty list of dots")
    output: list[str] = []
    for cell in cells:
        if not isinstance(cell, list) or len(cell) != len(set(cell)) or any(
            not isinstance(dot, int) or not 1 <= dot <= 6 for dot in cell
        ):
            raise ValueError("braille dots must be unique integers in 1..6")
        symbol = _BRAILLE.get(frozenset(cell))
        if symbol is None:
            raise ValueError("unknown six-dot braille cell")
        output.append(symbol)
    return "".join(output)


def playfair_codec(
    text: str,
    *,
    keyword: str,
    operation: str,
    padding: str = "X",
) -> dict[str, Any]:
    if operation not in {"encode", "decode"}:
        raise ValueError("operation must be encode or decode")
    padding = padding.upper()
    if len(padding) != 1 or not "A" <= padding <= "Z" or padding == "J":
        raise ValueError("padding must be one A-Z letter other than J")

    def clean(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Playfair input must be text")
        return "".join(character for character in value.upper().replace("J", "I") if "A" <= character <= "Z")

    alphabet = "ABCDEFGHIKLMNOPQRSTUVWXYZ"
    key_stream = clean(keyword) + alphabet
    square = "".join(dict.fromkeys(key_stream))
    positions = {character: divmod(index, 5) for index, character in enumerate(square)}
    cleaned = clean(text)
    digraphs: list[str] = []
    if operation == "encode":
        index = 0
        while index < len(cleaned):
            left = cleaned[index]
            right = cleaned[index + 1] if index + 1 < len(cleaned) else padding
            if left == right:
                right = padding
                index += 1
            else:
                index += 2
            digraphs.append(left + right)
    else:
        if len(cleaned) % 2:
            raise ValueError("Playfair decode text must have even length")
        digraphs = [cleaned[index:index + 2] for index in range(0, len(cleaned), 2)]
    shift = 1 if operation == "encode" else -1
    output: list[str] = []
    for pair in digraphs:
        (row_a, col_a), (row_b, col_b) = positions[pair[0]], positions[pair[1]]
        if row_a == row_b:
            output.extend((square[row_a * 5 + (col_a + shift) % 5],
                           square[row_b * 5 + (col_b + shift) % 5]))
        elif col_a == col_b:
            output.extend((square[((row_a + shift) % 5) * 5 + col_a],
                           square[((row_b + shift) % 5) * 5 + col_b]))
        else:
            output.extend((square[row_a * 5 + col_b], square[row_b * 5 + col_a]))
    return {"output": "".join(output), "digraphs": digraphs, "square": square}


def decode_token_morse(
    groups: list[list[str]], *, dot_token: str, dash_token: str
) -> dict[str, Any]:
    if not isinstance(dot_token, str) or not isinstance(dash_token, str) or not dot_token or not dash_token:
        raise ValueError("dot_token and dash_token must be non-empty strings")
    if dot_token == dash_token:
        raise ValueError("dot and dash tokens must be distinct")
    if not isinstance(groups, list) or not groups or len(groups) > 100:
        raise ValueError("groups must be a bounded non-empty list")
    patterns: list[str] = []
    for group in groups:
        if not isinstance(group, list) or not group or len(group) > 5:
            raise ValueError("each Morse group must contain 1..5 tokens")
        pattern: list[str] = []
        for token in group:
            if token == dot_token:
                pattern.append(".")
            elif token == dash_token:
                pattern.append("-")
            else:
                raise ValueError("Morse group contains an unknown token")
        patterns.append("".join(pattern))
    output = decode_morse(" ".join(patterns))
    if output is None:
        raise ValueError("token groups do not form valid Morse symbols")
    return {
        "output": output,
        "patterns": patterns,
        "dot_token": dot_token,
        "dash_token": dash_token,
    }


def solution_position_analysis(solutions: list[str]) -> dict[str, Any]:
    if not isinstance(solutions, list) or not 2 <= len(solutions) <= 100 or not all(
        isinstance(item, str) for item in solutions
    ):
        raise ValueError("solutions must contain 2..100 strings")
    lengths = {len(item) for item in solutions}
    if len(lengths) != 1:
        raise ValueError("solutions must have equal length")
    width = next(iter(lengths))
    if width > 10_000:
        raise ValueError("solutions must be bounded")
    invariant: list[dict[str, Any]] = []
    varying: list[dict[str, Any]] = []
    carrier: list[str] = []
    for index in range(width):
        values = sorted({item[index] for item in solutions})
        if len(values) == 1:
            invariant.append({"position": index + 1, "value": values[0]})
            carrier.append(values[0])
        else:
            varying.append({"position": index + 1, "values": values})
            carrier.append("?")
    return {
        "output": "".join(carrier),
        "invariant_positions": invariant,
        "varying_positions": varying,
        "solution_count": len(solutions),
    }


def palindrome_mismatch(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("text must be a bounded string")
    mismatches: list[dict[str, Any]] = []
    positions: set[int] = set()
    for left in range(len(text) // 2):
        right = len(text) - left - 1
        if text[left] != text[right]:
            mismatches.append({
                "left_position": left + 1,
                "left": text[left],
                "right_position": right + 1,
                "right": text[right],
            })
            positions.update((left, right))
    return {
        "output": "".join(text[index] for index in sorted(positions)),
        "mismatches": mismatches,
        "is_palindrome": not mismatches,
    }


def unicode_inspect(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or len(text) > 10_000:
        raise ValueError("text must be a bounded string")
    return {"output": [{
        "position": index + 1,
        "character": character,
        "codepoint": f"U+{ord(character):04X}",
        "name": unicodedata.name(character, "UNKNOWN"),
        "category": unicodedata.category(character),
    } for index, character in enumerate(text)]}


def minesweeper_propagate(grid: list[str]) -> dict[str, Any]:
    if not isinstance(grid, list) or not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must be a non-empty rectangular list of strings")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid must be rectangular")
    if len(grid) * width > 2_500:
        raise ValueError("grid must be bounded to 2500 cells")
    if any(character not in "012345678?*" for row in grid for character in row):
        raise ValueError("grid cells must use digits 0-8, ? for unknown, or * for mine")

    height = len(grid)
    input_mines = {
        (row, column)
        for row, value in enumerate(grid)
        for column, character in enumerate(value)
        if character == "*"
    }
    unknown = {
        (row, column)
        for row, value in enumerate(grid)
        for column, character in enumerate(value)
        if character == "?"
    }
    inferred_safe: set[tuple[int, int]] = set()
    inferred_mines: set[tuple[int, int]] = set()
    iterations = 0

    def neighbors(row: int, column: int) -> set[tuple[int, int]]:
        return {
            (near_row, near_column)
            for near_row in range(max(0, row - 1), min(height, row + 2))
            for near_column in range(max(0, column - 1), min(width, column + 2))
            if (near_row, near_column) != (row, column)
        }

    while True:
        known_mines = input_mines | inferred_mines
        undecided = unknown - inferred_safe - inferred_mines
        proposed_safe: set[tuple[int, int]] = set()
        proposed_mines: set[tuple[int, int]] = set()
        for row, value in enumerate(grid):
            for column, character in enumerate(value):
                if not character.isdigit():
                    continue
                adjacent = neighbors(row, column)
                adjacent_mines = len(adjacent & known_mines)
                adjacent_unknown = adjacent & undecided
                clue = int(character)
                if adjacent_mines > clue or adjacent_mines + len(adjacent_unknown) < clue:
                    raise ValueError(f"grid is inconsistent at clue [{row}, {column}]")
                remaining_mines = clue - adjacent_mines
                if remaining_mines == 0:
                    proposed_safe.update(adjacent_unknown)
                elif remaining_mines == len(adjacent_unknown):
                    proposed_mines.update(adjacent_unknown)
        conflict = proposed_safe & proposed_mines
        if conflict:
            row, column = min(conflict)
            raise ValueError(f"grid is inconsistent at cell [{row}, {column}]")
        proposed_safe.difference_update(inferred_safe)
        proposed_mines.difference_update(inferred_mines)
        if not proposed_safe and not proposed_mines:
            break
        inferred_safe.update(proposed_safe)
        inferred_mines.update(proposed_mines)
        iterations += 1

    remaining = unknown - inferred_safe - inferred_mines
    rendered = [list(row) for row in grid]
    for row, column in inferred_safe:
        rendered[row][column] = "."
    for row, column in inferred_mines:
        rendered[row][column] = "*"
    return {
        "output": ["".join(row) for row in rendered],
        "safe": [list(coordinate) for coordinate in sorted(inferred_safe)],
        "mines": [list(coordinate) for coordinate in sorted(inferred_mines)],
        "known_mines": [list(coordinate) for coordinate in sorted(input_mines)],
        "remaining_unknown": len(remaining),
        "stalled": bool(remaining),
        "iterations": iterations,
    }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    function: Callable[..., Any]
    deterministic: bool = True
    contract: str = ""


class ToolRegistry:
    def __init__(self):
        self._specs = {
            spec.name: spec for spec in (
                ToolSpec("extract_nth", extract_nth, contract="lines and 1-based indices are equal-length lists"),
                ToolSpec("anagram_delta", anagram_delta, contract="removed must be a character-multiset subset of source"),
                ToolSpec("read_grid_path", read_grid_path, contract="grid is list[str]; path is adjacent 0-based [row,col] list"),
                ToolSpec("dependency_order", dependency_order, contract="dependencies is node->list[prerequisite]; include leaf nodes with []"),
                ToolSpec("caesar_shift", caesar_shift, contract="shift is explicit integer -25..25; negative decodes a forward shift"),
                ToolSpec("atbash_transform", atbash_transform, contract="text is transformed with the self-inverse Latin alphabet mapping"),
                ToolSpec("base_decode", base_decode, contract="base is explicit 16|32|64; decoded bytes must be valid UTF-8"),
                ToolSpec("morse_decode", morse_decode, contract="text uses explicit dots/dashes; spaces separate letters and slash or double-space separates words"),
                ToolSpec("vigenere_decode", vigenere_decode, contract="key is known and explicit; this tool does not guess keys"),
                ToolSpec("rail_fence_decode", rail_fence_decode, contract="rails is known and explicit integer 2..100; this tool does not guess rail count"),
                ToolSpec("cipher_reference_lookup", lookup_cipher_reference, contract="query is an explicit cipher keyword; returns the matching rule and bounded reference table"),
                ToolSpec("a1z26_decode", a1z26_decode, contract="values is non-empty list[int] in 1..26"),
                ToolSpec("interleave_sequences", interleave_sequences, contract="sequences is list of at least two equal-length strings"),
                ToolSpec("grid_trace", grid_trace, contract="grid is list[str], start is 0-based [row,col], directions uses N|E|S|W"),
                ToolSpec("constrained_order", constrained_order, contract="constraints objects use type before|immediately_before with left/right or start|end with item"),
                ToolSpec("decode_bit_patterns", decode_bit_patterns, contract="patterns is equal-width bit-string list; bit_order is msb|lsb"),
                ToolSpec("repair_mojibake", repair_mojibake, contract="current_codec/original_codec name the strict reversible encode/decode path"),
                ToolSpec("bounded_mojibake_scan", bounded_mojibake_scan, contract="text is explicit and <=4096 chars; max_depth is 1|2; candidates are reversible and unscored"),
                ToolSpec("common_symbol_intersection", common_symbol_intersection, contract="values has >=2 strings; normalization is none|NFC|NFKC"),
                ToolSpec("grid_transform", grid_transform, contract="operation is transpose|rotate90|rotate180|rotate270|flip_h|flip_v"),
                ToolSpec("phone_keypad_decode", phone_keypad_decode, contract="groups is repeated-digit multitap strings such as ['44','33']"),
                ToolSpec("braille_decode", braille_decode, contract="cells is list of unique dot-number lists using 1..6"),
                ToolSpec("playfair_codec", playfair_codec, contract="operation is encode|decode; keyword explicit; I/J share a cell"),
                ToolSpec("decode_token_morse", decode_token_morse, contract="groups is list[list[token]]; dot_token and dash_token are distinct explicit strings"),
                ToolSpec("solution_position_analysis", solution_position_analysis, contract="solutions is 2..100 equal-length strings, not one candidate"),
                ToolSpec("palindrome_mismatch", palindrome_mismatch, contract="text is compared at mirrored character positions"),
                ToolSpec("unicode_inspect", unicode_inspect, contract="text returns codepoint/name/category records; it does not decode semantics"),
                ToolSpec("minesweeper_propagate", minesweeper_propagate, contract="grid is <=2500 rectangular cells using 0-8|?|*; returns only deterministic 8-neighbor deductions"),
            )
        }

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    @property
    def signatures(self) -> tuple[str, ...]:
        result: list[str] = []
        for name in sorted(self._specs):
            parameters = [
                parameter.name
                for parameter in inspect.signature(self._specs[name].function).parameters.values()
                if parameter.kind not in {
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                }
            ]
            signature = f"{name}({', '.join(parameters)})"
            contract = self._specs[name].contract
            result.append(f"{signature}: {contract}" if contract else signature)
        return tuple(result)

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
