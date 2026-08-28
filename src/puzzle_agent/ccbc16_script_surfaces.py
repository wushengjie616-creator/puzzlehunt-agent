"""Deterministic, answer-excluding adapters for CCBC16 text-backed scripts."""

from __future__ import annotations

from html import unescape
import json
import re


SCRIPT_SURFACE_URLS = {
    46: "https://ccbc16.cipherpuzzles.com/data/puzzle_script/c16-triddles.js",
    48: "https://ccbc16.cipherpuzzles.com/data/puzzle_script/c16-brackets.js",
}

_STRING = r'"(?:\\.|[^"\\])*"'
_TRIDDLE = re.compile(
    rf"\{{\s*id:\s*(\d+)\s*,\s*gram:\s*({_STRING})\s*,\s*ans:\s*{_STRING}"
    rf"(?:\s*,\s*extra:\s*({_STRING}))?\s*\}}"
)
_BRACKET = re.compile(
    rf"\{{\s*clue:\s*({_STRING})\s*,\s*ans:\s*{_STRING}\s*,"
    rf"\s*id:\s*(\d+)\s*,\s*g:\s*(\d+)\s*\}}"
)


def _literal(value: str) -> str:
    decoded = json.loads(value)
    if not isinstance(decoded, str):
        raise ValueError("script surface contains a non-string clue")
    return decoded


def _visible_clue(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    if re.search(r"<[A-Za-z/][^>]*>", value):
        raise ValueError("script surface contains unsupported clue markup")
    return unescape(value).strip()


def _triddles(source: str) -> str:
    groups: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in source.splitlines():
        if "levels:" in line:
            current = {"clues": [], "next": None}
            groups.append(current)
        match = _TRIDDLE.search(line)
        if match:
            if current is None:
                raise ValueError("triddles clue appears outside a level group")
            clue_id, gram_raw, extra_raw = match.groups()
            clue = {
                "id": int(clue_id),
                "clue": _visible_clue(_literal(gram_raw)),
                "extra": _visible_clue(_literal(extra_raw)) if extra_raw else None,
            }
            current["clues"].append(clue)  # type: ignore[union-attr]
        next_match = re.search(rf"\bnext:\s*({_STRING})", line)
        if next_match and current is not None:
            current["next"] = _literal(next_match.group(1))
    groups = [group for group in groups if group["clues"]]
    if not groups:
        raise ValueError("script surface contains no public clues")
    lines = [
        "以下是官方公开的分阶段三字谜题面。阶段与 ID 顺序必须保留；答案提交会解锁后续阶段。",
    ]
    for index, group in enumerate(groups, 1):
        lines.append(f"\n阶段 {index} [next={group['next'] or 'unspecified'}]")
        for clue in group["clues"]:  # type: ignore[union-attr]
            suffix = f" [提示={clue['extra']}]" if clue["extra"] else ""
            lines.append(f"- [id={clue['id']}] {clue['clue']}{suffix}")
    return "\n".join(lines)


def _brackets(source: str) -> str:
    groups: dict[int, list[tuple[int, str]]] = {}
    for match in _BRACKET.finditer(source):
        clue_raw, clue_id, group_id = match.groups()
        groups.setdefault(int(group_id), []).append(
            (int(clue_id), _visible_clue(_literal(clue_raw)))
        )
    if not groups:
        raise ValueError("script surface contains no public clues")
    lines = [
        "以下是官方公开的括号谜题面。所有括号均保留原始 Unicode 码位；组序与 ID 必须保留。",
    ]
    for group_id in sorted(groups):
        lines.append(f"\n组 {group_id}")
        for clue_id, clue in groups[group_id]:
            lines.append(f"- [id={clue_id}] {clue}")
    return "\n".join(lines)


def extract_script_surface(puzzle_id: int, source: str) -> str:
    """Extract a public initial surface without serializing answer fields."""

    if not isinstance(source, str):
        raise ValueError("script surface source must be text")
    if puzzle_id == 46:
        return _triddles(source)
    if puzzle_id == 48:
        return _brackets(source)
    raise ValueError(f"puzzle {puzzle_id} has no supported script surface adapter")
