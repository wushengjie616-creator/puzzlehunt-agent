#!/usr/bin/env python3
"""Generate the original general-puzzle demo images."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1] / "examples" / "general-puzzle-demos"
WIDTH, HEIGHT = 1200, 960
PAPER, INK, MUTED, ACCENT = "#fffdf7", "#17211f", "#63706b", "#b64b33"


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


TITLE, SUBTITLE, BODY, MONO = font(48, bold=True), font(25), font(27), font(35, bold=True)


def canvas(title: str, subtitle: str):
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((62, 42), title, fill=INK, font=TITLE)
    draw.text((64, 108), subtitle, fill=MUTED, font=SUBTITLE)
    draw.line((62, 150, WIDTH - 62, 150), fill=INK, width=3)
    return image, draw


def centered(draw, box, text, face=BODY, fill=INK):
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), text, font=face)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    draw.text(((left + right - width) / 2, (top + bottom - height) / 2 - 3), text, font=face, fill=fill)


def case_shift_change():
    image, draw = canvas("风暴灯语", "暴风封港那夜，守灯人留下十三张五字母潮汐牌")
    tokens = ["TiDes", "WaVeS", "ShoRe", "nORTh", "buoYs", "nighT", "fogGY",
              "cLoCK", "TiDes", "sHore", "LigHt", "waVeS", "tiDeS"]
    for index, token in enumerate(tokens):
        row, column = divmod(index, 7)
        left, top = 45 + column * 162, 188 + row * 94
        draw.rounded_rectangle((left, top, left + 142, top + 66), radius=11, outline=INK, width=2)
        centered(draw, (left, top, left + 142, top + 66), token, face=MONO)
    draw.text((70, 410), "白昼的墨迹很浅，入夜后只有“大写的窗”会亮。", fill=INK, font=BODY)
    draw.text((70, 463), "旧港规：先看最西边那扇窗；每五扇窗只合报一次。", fill=INK, font=BODY)
    draw.rounded_rectangle((315, 565, 885, 740), radius=16, outline=ACCENT, width=4)
    centered(draw, (315, 578, 885, 628), "锈蚀字母盘", face=SUBTITLE, fill=ACCENT)
    centered(draw, (315, 625, 885, 690), "KDUERU", face=MONO)
    centered(draw, (315, 690, 885, 732), "“它总把字母送向错误的一侧。”", face=SUBTITLE, fill=MUTED)
    draw.text((870, 850), "港名：（6）", fill=MUTED, font=BODY)
    image.save(ROOT / "case-shift-change" / "puzzle.png", optimize=False)


def night_watch_order():
    image, draw = canvas("最后一班守灯人", "旧灯塔封存前，七张交接牌散落在桌上")
    cards = [("Owl", "TOWER", 3), ("Fox", "GUARD", 2), ("Stag", "SQUALL", 2), ("Moth", "SHORE", 3),
             ("Hare", "EQUAL", 2), ("Lynx", "GHOST", 2), ("Crow", "ADORE", 2)]
    for index, (name, word, lanterns) in enumerate(cards):
        row, column = divmod(index, 4)
        left, top = 55 + column * 258, 180 + row * 92
        draw.rounded_rectangle((left, top, left + 235, top + 68), radius=10, outline=INK, width=2)
        centered(draw, (left, top, left + 235, top + 68), f"{name} · {word}  {'●' * lanterns}", face=SUBTITLE)
    rules = [
        "1. Moth 带钥匙开门；Stag 检查完所有人后锁门。",
        "2. Crow 把日志直接交到 Hare 手里，中间没人碰过。",
        "3. Hare 离开后 Owl 才能登塔。",
        "4. Owl 校准镜片后，Lynx 才去机房。",
        "5. Lynx 出来就把工具直接交给 Fox。",
    ]
    draw.text((75, 378), "灯标数 = 口令响钟的拍数", fill=ACCENT, font=SUBTITLE)
    draw.text((75, 426), "交接记录", fill=ACCENT, font=BODY)
    for index, line in enumerate(rules):
        draw.text((90, 478 + index * 48), line, fill=INK, font=SUBTITLE)
    draw.rounded_rectangle((125, 742, 1000, 825), radius=12, outline=ACCENT, width=3)
    centered(draw, (125, 742, 1000, 825), "墙上的铜制字母盘比标准字母表“慢了三格”。", face=BODY, fill=ACCENT)
    draw.text((885, 870), "失踪器材：（7）", fill=MUTED, font=BODY)
    image.save(ROOT / "night-watch-order" / "puzzle.png", optimize=False)


def mirror_calibration():
    image, draw = canvas("镜廊失窃案", "闭馆后暗格被打开；镜匠留下六条校准纹")
    rows = ["GBCDCBA", "QPTRTAQ", "QRMUARQ", "MDEYEDA", "HPJKJAH", "LMXNAML"]
    draw.text((72, 175), "镜纹左右相合；每面只裂一对。用 A—Z 刻尺量裂口间距，再把刻度当字母读。", fill=INK, font=SUBTITLE)
    for index, row in enumerate(rows):
        top = 245 + index * 78
        draw.rounded_rectangle((80, top, 515, top + 56), radius=8, outline=INK, width=2)
        centered(draw, (80, top, 515, top + 56), row, face=MONO)
    grid = ["QAZWS", "XSECV", "P★MRO", "KJTEB", "NHGFD"]
    x, y, cell = 650, 255, 78
    draw.text((650, 215), "暗格字盘", fill=ACCENT, font=BODY)
    for row in range(6):
        draw.line((x, y + row * cell, x + 5 * cell, y + row * cell), fill=INK, width=2)
    for column in range(6):
        draw.line((x + column * cell, y, x + column * cell, y + 5 * cell), fill=INK, width=2)
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            centered(draw, (x + column * cell, y + row * cell, x + (column + 1) * cell, y + (row + 1) * cell), value, face=MONO, fill=ACCENT if value == "★" else INK)
    centered(draw, (625, 695, 1085, 770), "↑  →  →  ↓  ↓  ←", face=MONO, fill=ACCENT)
    draw.text((845, 870), "暗格标签：（6）", fill=MUTED, font=BODY)
    image.save(ROOT / "mirror-calibration" / "puzzle.png", optimize=False)


def main():
    case_shift_change()
    night_watch_order()
    mirror_calibration()


if __name__ == "__main__":
    main()
