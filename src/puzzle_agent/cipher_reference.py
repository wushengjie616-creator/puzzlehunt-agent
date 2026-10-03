"""Bounded, deterministic reference data and transforms for puzzle ciphers."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .cipher_workbench import caesar_decode, decode_ascii_decimal, decode_bacon


_MAX_TEXT = 10_000


def _bacon_table() -> list[dict[str, str]]:
    return [
        {"letter": chr(ord("A") + index), "code": format(index, "05b").replace("0", "a").replace("1", "b")}
        for index in range(26)
    ]


_BRAILLE = {
    "A": "1", "B": "12", "C": "14", "D": "145", "E": "15",
    "F": "124", "G": "1245", "H": "125", "I": "24", "J": "245",
    "K": "13", "L": "123", "M": "134", "N": "1345", "O": "135",
    "P": "1234", "Q": "12345", "R": "1235", "S": "234", "T": "2345",
    "U": "136", "V": "1236", "W": "2456", "X": "1346", "Y": "13456", "Z": "1356",
}

_BRAILLE_DIGITS = {
    "1": "1", "2": "12", "3": "14", "4": "145", "5": "15",
    "6": "124", "7": "1245", "8": "125", "9": "24", "0": "245",
}

BRAILLE_TABLE = (
    [{"label": label, "dots": dots, "kind": "letter"} for label, dots in _BRAILLE.items()]
    + [{"label": label, "dots": dots, "kind": "digit"} for label, dots in _BRAILLE_DIGITS.items()]
)

_DIRECTION_LABELS = {
    "N": "上", "NE": "右上", "E": "右", "SE": "右下",
    "S": "下", "SW": "左下", "W": "左", "NW": "左上",
}

# Receiver-view vectors, cross-checked against the U.S. Navy Signalman Appendix II
# and the Australian government semaphore reference. Left/right labels name the
# signaller's hands; across-body poses are represented by their visible endpoint.
_SEMAPHORE_DIRECTIONS = {
    "A": ("S", "SW"), "B": ("S", "W"), "C": ("S", "NW"), "D": ("S", "N"),
    "E": ("NE", "S"), "F": ("E", "S"), "G": ("SE", "S"), "H": ("SW", "W"),
    "I": ("SW", "N"), "J": ("E", "N"), "K": ("N", "SW"), "L": ("NE", "SW"),
    "M": ("E", "SW"), "N": ("SE", "SW"), "O": ("NW", "W"), "P": ("N", "W"),
    "Q": ("NE", "W"), "R": ("E", "W"), "S": ("SE", "W"), "T": ("N", "NW"),
    "U": ("NE", "NW"), "V": ("SE", "N"), "W": ("E", "NE"), "X": ("SE", "NE"),
    "Y": ("E", "NW"), "Z": ("E", "SE"),
}

SEMAPHORE_TABLE = [
    {
        "letter": letter,
        "left": left,
        "right": right,
        "left_label": _DIRECTION_LABELS[left],
        "right_label": _DIRECTION_LABELS[right],
    }
    for letter, (left, right) in _SEMAPHORE_DIRECTIONS.items()
]


_PIGPEN_TABLE = [
    {
        "letter": chr(ord("A") + index),
        "family": "井字格" if index < 18 else "X 格",
        "position": (
            ["左上", "上中", "右上", "左中", "中央", "右中", "左下", "下中", "右下"][index % 9]
            if index < 18 else ["上", "右", "下", "左"][(index - 18) % 4]
        ),
        "dotted": index in range(9, 18) or index >= 22,
    }
    for index in range(26)
]


_REFERENCES = (
    {
        "id": "bacon", "name": "培根密码", "aliases": ["Bacon", "培根", "A/B"],
        "summary": "把字母写成五位 a/b（或任意两种状态）组合。",
        "rule": "现代 26 字母表可按 A=aaaaa 到 Z=bbaab；每五位一组。",
        "cautions": "古典 24 字母版本会合并 I/J 与 U/V，解题时必须先看题面采用哪种变体。",
        "table": _bacon_table(),
        "visual": "compact-grid",
    },
    {
        "id": "pigpen", "name": "猪圈密码", "aliases": ["Pigpen", "共济会", "猪圈"],
        "summary": "用井字格和 X 格的边角形状表示字母，第二轮通常加点。",
        "rule": "A–R 放入两轮 3×3 井字格，S–Z 放入两轮 X 格；同位置第二轮加点。",
        "cautions": "不同资料可能交换字母顺序或旋转图形；先用题面中的重复符号验证字母表方向。",
        "table": _PIGPEN_TABLE,
        "visual": "pigpen-image",
    },
    {
        "id": "caesar", "name": "凯撒密码", "aliases": ["Caesar", "ROT", "移位"],
        "summary": "把英文字母在 26 字母表中统一平移。",
        "rule": "解码 shift=n 时，每个字母向前移动 n 位；ROT13 是 shift=13。",
        "cautions": "标点和大小写通常保留；出现不同字母使用不同位移时就不是单一凯撒密码。",
        "table": [{"shift": shift, "mapping": f"A→{chr(ord('A') + (-shift) % 26)}"} for shift in range(26)],
        "visual": "none",
    },
    {
        "id": "rail_fence", "name": "栅栏密码", "aliases": ["Rail Fence", "栅栏", "篱笆"],
        "summary": "按锯齿路径写入若干栏，再逐栏读出。",
        "rule": "解码必须知道栏数；常见题可在小范围栏数中逐一核对，但候选不是答案证明。",
        "cautions": "注意空格是否参与、起始方向、偏移和普通分栏转置并非同一种规则。",
        "table": [{"rails": rails, "cycle": 2 * rails - 2} for rails in range(2, 7)],
        "visual": "none",
    },
    {
        "id": "ascii", "name": "ASCII", "aliases": ["ASCII", "字符码", "十进制编码"],
        "summary": "用 0–127 的整数表示英文字符和控制字符。",
        "rule": "谜题常用十进制、十六进制或二进制写 ASCII；例如 65、0x41、1000001 都是 A。",
        "cautions": "大于 127 的值可能是扩展编码或 Unicode，不能继续按标准 ASCII 强解。",
        "table": [
            {"character": chr(value), "decimal": value, "binary": format(value, "07b"), "hex": format(value, "02X")}
            for value in range(32, 127)
        ],
        "visual": "compact-grid",
    },
    {
        "id": "semaphore", "name": "旗语", "aliases": ["Semaphore", "手旗", "旗语"],
        "summary": "用两面手旗的固定方向组合表示字母。",
        "rule": "面对发信者读取；每条手臂只使用八个 45° 方向，姿势必须停稳后再读。",
        "cautions": "左右手以发信者自身为准，接收者看到的是镜像；数字通常先发送数字标志，再复用字母姿势。",
        "table": SEMAPHORE_TABLE,
        "visual": "semaphore",
    },
)


_BRAILLE_REFERENCE = {
    "id": "braille",
    "name": "盲文",
    "aliases": ["Braille", "点字", "六点盲文"],
    "summary": "用六个点位的凸点组合表示字母和数字。",
    "rule": "点位从左上到左下为 1–3、右上到右下为 4–6；数字需先识别数字标志 3456。",
    "cautions": "数字 1–0 复用字母 A–J 的点位；没有数字标志时不能仅凭单格断定字母或数字。",
    "table": BRAILLE_TABLE,
    "visual": "braille",
}

_A1Z26_REFERENCE = {
    "id": "a1z26",
    "name": "A1Z26",
    "aliases": ["字母序号", "Alphabet numbers", "1-26"],
    "summary": "按英文字母顺序用 1–26 表示 A–Z。",
    "rule": "A=1、B=2，依次到 Z=26；分隔符和分组通常由题面决定。",
    "cautions": "连续数字可能有多种切分，必须用题面分隔、长度或语言证据验证。",
    "table": [
        {"letter": chr(ord("A") + index), "number": index + 1}
        for index in range(26)
    ],
    "visual": "compact-grid",
}

_AGENT_REFERENCES = {
    item["id"]: item for item in (*_REFERENCES, _BRAILLE_REFERENCE, _A1Z26_REFERENCE)
}

_AGENT_REFERENCE_PATTERNS = (
    ("bacon", (r"培根(?:密码|编码)?", r"\bbacon(?:ian)?\b", r"\ba\s*/\s*b\b")),
    ("pigpen", (r"猪圈(?:密码|编码)?", r"共济会(?:密码)?", r"\bpigpen\b")),
    ("caesar", (r"凯撒(?:密码|移位)?", r"字母移位", r"\bcaesar\b", r"\brot[- ]?\d{1,2}\b")),
    ("rail_fence", (r"栅栏(?:密码|编码)?", r"篱笆(?:密码)?", r"\brail[ -]?fence\b")),
    ("ascii", (r"\bascii\b", r"字符码", r"十进制编码")),
    ("braille", (r"盲文", r"点字", r"六点(?:排列|编码)", r"\bbraille\b")),
    ("semaphore", (r"旗语", r"手旗", r"\bsemaphore\b")),
    ("a1z26", (r"\ba1z26\b", r"字母序号", r"\b1\s*[-–—]\s*26\b")),
)


def index_cipher_references(text: str) -> list[dict[str, Any]]:
    """Return compact routing hints for explicit cipher keywords in puzzle text."""
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("text must be a string bounded to 100000 characters")
    hints: list[dict[str, Any]] = []
    for reference_id, patterns in _AGENT_REFERENCE_PATTERNS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            item = _AGENT_REFERENCES[reference_id]
            hints.append({
                "id": item["id"],
                "name": item["name"],
                "summary": item["summary"],
                "rule": item["rule"],
                "cautions": item["cautions"],
                "lookup_query": item["name"],
            })
    return hints


def lookup_cipher_reference(query: str) -> dict[str, Any]:
    """Return bounded full reference records for an explicit Agent query."""
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        raise ValueError("query must be a non-empty string bounded to 100 characters")
    matched_ids = [item["id"] for item in index_cipher_references(query)]
    if not matched_ids:
        matched_ids = [item["id"] for item in search_references(query)]
    matched_ids = list(dict.fromkeys(matched_ids))[:4]
    if not matched_ids:
        raise ValueError("no cipher reference matched the query")
    items = [deepcopy(_AGENT_REFERENCES[reference_id]) for reference_id in matched_ids]
    return {"output": items, "query": query.strip(), "match_count": len(items)}


def search_references(query: str = "") -> list[dict[str, Any]]:
    if not isinstance(query, str) or len(query) > 100:
        raise ValueError("query must be a string bounded to 100 characters")
    needle = query.strip().casefold()
    if not needle:
        return [dict(item) for item in _REFERENCES]
    return [
        dict(item) for item in _REFERENCES
        if needle in " ".join([
            item["id"], item["name"], *item["aliases"], item["summary"], item["rule"], item["cautions"],
        ]).casefold()
    ]


def _text(payload: dict[str, Any]) -> str:
    text = payload.get("text")
    if not isinstance(text, str) or not text or len(text) > _MAX_TEXT:
        raise ValueError(f"text must be a non-empty string bounded to {_MAX_TEXT} characters")
    return text


def _tokens(text: str) -> list[str]:
    tokens = [token for token in re.split(r"[\s,;|/-]+", text.strip()) if token]
    if not tokens or len(tokens) > 2048:
        raise ValueError("input must contain 1..2048 tokens")
    return tokens


def _encode_letters(text: str, table: dict[str, str], *, separator: str = " ") -> str:
    words: list[str] = []
    for word in text.upper().split():
        if not word.isascii() or not word.isalpha():
            raise ValueError("text must contain ASCII letters and spaces only")
        words.append(separator.join(table[letter] for letter in word))
    if not words:
        raise ValueError("text must contain at least one letter")
    return " / ".join(words)


def transform(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    operation = payload.get("operation")
    text = _text(payload)

    if operation == "caesar_all":
        return {"operation": operation, "rows": [
            {"shift": shift, "output": caesar_decode(text, shift)} for shift in range(26)
        ]}

    bacon = {item["letter"]: item["code"] for item in _bacon_table()}
    if operation == "bacon_encode":
        return {"operation": operation, "variant": "modern-26", "output": _encode_letters(text, bacon)}
    if operation == "bacon_decode":
        output = decode_bacon(text)
        if output is None:
            raise ValueError("Bacon input must contain valid a/b groups of five")
        return {"operation": operation, "variant": "modern-26", "output": output}

    a1z26 = {chr(ord("A") + index): str(index + 1) for index in range(26)}
    if operation == "a1z26_encode":
        return {"operation": operation, "output": _encode_letters(text, a1z26, separator="-")}
    if operation == "a1z26_decode":
        words = []
        for raw_word in re.split(r"\s*/\s*", text.strip()):
            values = _tokens(raw_word)
            if any(not value.isdigit() or not 1 <= int(value) <= 26 for value in values):
                raise ValueError("A1Z26 values must be integers in 1..26")
            words.append("".join(chr(ord("A") + int(value) - 1) for value in values))
        return {"operation": operation, "output": " ".join(words)}

    if operation == "ascii_encode":
        if any(ord(character) > 127 for character in text):
            raise ValueError("ASCII encode accepts code points in 0..127 only")
        return {"operation": operation, "output": " ".join(str(ord(character)) for character in text)}
    if operation == "ascii_decode":
        if re.search(r"(^|[\s,;|/])-\d", text):
            raise ValueError("ASCII values must be decimal integers in 0..127")
        output = decode_ascii_decimal(text)
        if output is None:
            raise ValueError("ASCII values must be decimal integers in 0..127")
        return {"operation": operation, "output": output}

    if operation == "braille_encode":
        return {"operation": operation, "output": _encode_letters(text, _BRAILLE)}
    if operation == "braille_decode":
        reverse = {value: key for key, value in _BRAILLE.items()}
        words = []
        for raw_word in re.split(r"\s*/\s*", text.strip()):
            values = _tokens(raw_word)
            if any(value not in reverse for value in values):
                raise ValueError("Braille cells must use valid dot numbers 1..6")
            words.append("".join(reverse[value] for value in values))
        return {"operation": operation, "output": " ".join(words)}

    if operation == "radix_convert":
        source_base = payload.get("from_base")
        if source_base not in {2, 3, 10}:
            raise ValueError("from_base must be 2, 3, or 10")
        if re.search(r"(^|[\s,;|/])-\w", text):
            raise ValueError("numeric values must be non-negative")
        rows = []
        for token in _tokens(text):
            try:
                value = int(token, source_base)
            except ValueError as exc:
                raise ValueError(f"{token!r} is not valid base {source_base}") from exc
            if not 0 <= value <= 1_114_111:
                raise ValueError("numeric values must be in 0..1114111")
            rows.append({
                "input": token,
                "decimal": value,
                "binary": format(value, "b"),
                "ternary": _to_base(value, 3),
                "ascii": chr(value) if 0 <= value <= 127 else None,
            })
        return {"operation": operation, "from_base": source_base, "rows": rows}

    raise ValueError("unsupported cipher operation")


def _to_base(value: int, base: int) -> str:
    if value == 0:
        return "0"
    digits: list[str] = []
    while value:
        value, remainder = divmod(value, base)
        digits.append(str(remainder))
    return "".join(reversed(digits))
