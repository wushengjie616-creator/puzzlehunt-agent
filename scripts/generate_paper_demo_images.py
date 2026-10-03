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
    image, draw = canvas("4 x 4 Sudoku", "Fill 1-4; no repeats in rows, columns, or 2 x 2 boxes")
    draw_grid(draw, source["grid"], x=210, y=170, cell=120, box_rows=2, box_cols=2)
    image.save(case / "puzzle.png", optimize=False)


def nonogram(case: Path, source):
    image, draw = canvas("5 x 5 Nonogram", "Shade cells to satisfy every row and column clue")
    x, y, cell = 260, 230, 72
    grid = [[None] * 5 for _ in range(5)]
    draw_grid(draw, grid, x=x, y=y, cell=cell)
    for index, clue in enumerate(source["row_clues"]):
        centered(draw, (130, y + index * cell, x - 18, y + (index + 1) * cell), " ".join(map(str, clue)), face=BODY)
    for index, clue in enumerate(source["column_clues"]):
        centered(draw, (x + index * cell, 160, x + (index + 1) * cell, y - 12), " ".join(map(str, clue)), face=BODY)
    image.save(case / "puzzle.png", optimize=False)


def rule_grid(case: Path, source, title: str, subtitle: str, extras=()):
    image, draw = canvas(title, subtitle)
    display = source["display"]
    grid = [[None] * display["columns"] for _ in range(display["rows"])]
    for entity in source["entities"]:
        grid[entity["row"]][entity["column"]] = entity["value"]
    size = 100 if display["rows"] == 4 else 120
    width = display["columns"] * size
    x = (WIDTH - width) // 2
    draw_grid(draw, grid, x=x, y=190, cell=size)
    for text, position in extras:
        draw.text(position, text, fill=ACCENT, font=BODY)
    image.save(case / "puzzle.png", optimize=False)


def kakuro(case: Path, source):
    image, draw = canvas("Cross Sums", "Digits 1-4; digits in each sum are distinct")
    boxes = {"A": (300, 220), "B": (440, 220), "C": (300, 360), "D": (440, 360)}
    for label, (x, y) in boxes.items():
        draw.rounded_rectangle((x, y, x + 110, y + 110), radius=12, outline=INK, width=4)
        centered(draw, (x, y, x + 110, y + 110), label)
    draw.text((570, 238), "A + B = 4", fill=ACCENT, font=BODY)
    draw.text((570, 305), "A + C = 3", fill=ACCENT, font=BODY)
    draw.text((570, 372), "B + D = 7", fill=ACCENT, font=BODY)
    image.save(case / "puzzle.png", optimize=False)


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["cases"]:
        case = ROOT / item["id"]
        source = json.loads((case / "source.json").read_text(encoding="utf-8"))
        if item["engine"] == "sudoku":
            sudoku(case, source)
        elif item["engine"] == "nonogram":
            nonogram(case, source)
        elif item["puzzle_type"] == "futoshiki":
            rule_grid(case, source, "4 x 4 Futoshiki", "Rows and columns use 1-4; obey the inequality", [("R1C1 < R1C2", (340, 155))])
        elif item["puzzle_type"] == "skyscrapers":
            rule_grid(case, source, "3 x 3 Skyscrapers", "Edge clues: visible towers from that direction", [
                ("3  2  1", (365, 155)), ("1  2  2", (365, 570)),
                ("3", (230, 235)), ("2", (230, 355)), ("1", (230, 475)),
                ("1", (650, 235)), ("2", (650, 355)), ("2", (650, 475)),
            ])
        elif item["puzzle_type"] == "kakuro":
            kakuro(case, source)


if __name__ == "__main__":
    main()
