#!/usr/bin/env python3
"""Generate the original PNG fixtures under examples/paper-puzzle-demos."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1] / "examples" / "paper-puzzle-demos"
WIDTH, HEIGHT = 900, 680
INK, PAPER, MUTED, ACCENT = "#18201f", "#fffdf7", "#68716e", "#d34f2c"


def font(size: int, *, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size, index=0)
            except OSError:
                continue
    return ImageFont.load_default()


TITLE = font(40, bold=True)
BODY = font(23)
CELL = font(42, bold=True)
SMALL = font(18)


def canvas(title: str, subtitle: str):
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((54, 40), title, fill=INK, font=TITLE)
    draw.text((56, 96), subtitle, fill=MUTED, font=BODY)
    draw.line((54, 138, WIDTH - 54, 138), fill=INK, width=3)
    return image, draw


def centered(draw, box, text, *, fill=INK, face=CELL):
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), str(text), font=face)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    draw.text(((left + right - width) / 2, (top + bottom - height) / 2 - 3), str(text), fill=fill, font=face)


def draw_grid(draw, grid, *, x=190, y=180, cell=120, box_rows=None, box_cols=None):
    rows, columns = len(grid), len(grid[0])
    for row in range(rows + 1):
        width = 6 if row in {0, rows} or (box_rows and row % box_rows == 0) else 2
        draw.line((x, y + row * cell, x + columns * cell, y + row * cell), fill=INK, width=width)
    for column in range(columns + 1):
        width = 6 if column in {0, columns} or (box_cols and column % box_cols == 0) else 2
        draw.line((x + column * cell, y, x + column * cell, y + rows * cell), fill=INK, width=width)
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value is not None:
                centered(draw, (x + column * cell, y + row * cell, x + (column + 1) * cell, y + (row + 1) * cell), value)


def sudoku(case: Path, source):
    size = source["size"]
    cell = min(52, 468 // size)
    width = cell * size
    image, draw = canvas(
        f"{size} x {size} Sudoku",
        f"Fill 1-{size}; no repeats in rows, columns, or {source['box_rows']} x {source['box_cols']} boxes",
    )
    draw_grid(
        draw, source["grid"], x=(WIDTH - width) // 2, y=170, cell=cell,
        box_rows=source["box_rows"], box_cols=source["box_cols"],
    )
    image.save(case / "puzzle.png", optimize=False)


def nonogram(case: Path, source):
    rows, columns = len(source["row_clues"]), len(source["column_clues"])
    image, draw = canvas(f"{columns} x {rows} Nonogram", "Shade cells to satisfy every row and column clue")
    cell = min(39, 390 // max(rows, columns))
    x, y = 325, 235
    grid = [[None] * columns for _ in range(rows)]
    draw_grid(draw, grid, x=x, y=y, cell=cell)
    for index, clue in enumerate(source["row_clues"]):
        centered(draw, (80, y + index * cell, x - 15, y + (index + 1) * cell), " ".join(map(str, clue)), face=SMALL)
    for index, clue in enumerate(source["column_clues"]):
        centered(draw, (x + index * cell, 150, x + (index + 1) * cell, y - 8), "\n".join(map(str, clue)), face=SMALL)
    image.save(case / "puzzle.png", optimize=False)


def rule_grid(case: Path, source, title: str, subtitle: str):
    image, draw = canvas(title, subtitle)
    display = source["display"]
    grid = [[None] * display["columns"] for _ in range(display["rows"])]
    for entity in source["entities"]:
        grid[entity["row"]][entity["column"]] = entity["value"]
    size = min(92, 460 // max(display["rows"], display["columns"]))
    width = display["columns"] * size
    x = (WIDTH - width) // 2
    draw_grid(draw, grid, x=x, y=190, cell=size)
    return image, draw, x, 190, size


def futoshiki(case: Path, source):
    image, draw, x, y, size = rule_grid(
        case, source, "5 x 5 Futoshiki",
        "Rows and columns use 1-5; each symbol points toward the smaller value",
    )
    positions = {entity["id"]: (entity["row"], entity["column"]) for entity in source["entities"]}
    for clue in source["clues"]:
        smaller, larger = clue["entity_ids"]
        sr, sc = positions[smaller]
        lr, lc = positions[larger]
        if sr == lr:
            left_is_smaller = sc < lc
            symbol = "<" if left_is_smaller else ">"
            boundary = max(sc, lc)
            centered(draw, (x + boundary * size - 13, y + sr * size + 28,
                            x + boundary * size + 13, y + (sr + 1) * size - 28),
                     symbol, fill=ACCENT, face=SMALL)
        else:
            top_is_smaller = sr < lr
            symbol = "∧" if top_is_smaller else "∨"
            boundary = max(sr, lr)
            centered(draw, (x + sc * size + 28, y + boundary * size - 13,
                            x + (sc + 1) * size - 28, y + boundary * size + 13),
                     symbol, fill=ACCENT, face=SMALL)
    image.save(case / "puzzle.png", optimize=False)


def skyscrapers(case: Path, source, program):
    image, draw, x, y, size = rule_grid(
        case, source, "4 x 4 Skyscrapers",
        "Edge clues count visible towers; higher towers hide lower ones",
    )
    targets = {
        constraint["source_clue_ids"][0]: constraint["target"]
        for constraint in program["constraints"] if constraint["type"] == "visibility"
    }
    n = source["display"]["rows"]
    for index in range(n):
        centered(draw, (x + index * size, y - 45, x + (index + 1) * size, y - 5), targets[f"c{index + 1}t"], face=BODY)
        centered(draw, (x + index * size, y + n * size + 5, x + (index + 1) * size, y + n * size + 45), targets[f"c{index + 1}b"], face=BODY)
        centered(draw, (x - 45, y + index * size, x - 5, y + (index + 1) * size), targets[f"r{index + 1}l"], face=BODY)
        centered(draw, (x + n * size + 5, y + index * size, x + n * size + 45, y + (index + 1) * size), targets[f"r{index + 1}r"], face=BODY)
    image.save(case / "puzzle.png", optimize=False)


def kakuro(case: Path, source):
    image, draw = canvas("3 x 3 Cross Sums", "Fill 1-9; digits are distinct within every row and column sum")
    x, y, cell = 300, 220, 105
    grid = [[None] * 3 for _ in range(3)]
    for entity in source["entities"]:
        grid[entity["row"]][entity["column"]] = entity["value"]
    draw_grid(draw, grid, x=x, y=y, cell=cell)
    row_sums = [11, 23, 15]
    column_sums = [20, 10, 19]
    for index, value in enumerate(row_sums):
        centered(draw, (x - 70, y + index * cell, x - 12, y + (index + 1) * cell), value, fill=ACCENT, face=BODY)
    for index, value in enumerate(column_sums):
        centered(draw, (x + index * cell, y - 60, x + (index + 1) * cell, y - 10), value, fill=ACCENT, face=BODY)
    draw.text((625, 285), "row sums →", fill=MUTED, font=SMALL)
    draw.text((365, 555), "↑ column sums", fill=MUTED, font=SMALL)
    image.save(case / "puzzle.png", optimize=False)


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["cases"]:
        case = ROOT / item["id"]
        source = json.loads((case / "source.json").read_text(encoding="utf-8"))
        program = json.loads((case / "program.json").read_text(encoding="utf-8"))
        if item["engine"] == "sudoku":
            sudoku(case, source)
        elif item["engine"] == "nonogram":
            nonogram(case, source)
        elif item["puzzle_type"] == "futoshiki":
            futoshiki(case, source)
        elif item["puzzle_type"] == "skyscrapers":
            skyscrapers(case, source, program)
        elif item["puzzle_type"] == "kakuro":
            kakuro(case, source)


if __name__ == "__main__":
    main()
