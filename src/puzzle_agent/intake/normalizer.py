from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from puzzle_agent.paper_puzzle.components.sudoku import build_state, validate_spec
from puzzle_agent.paper_puzzle.components.nonogram import build_state as build_nonogram_state
from puzzle_agent.paper_puzzle.components.rule_based import RulePuzzleError, validate_source

from .contracts import canonical_hash


class NormalizationError(ValueError):
    """DeepSeek normalization output is invalid or unsupported."""


_SYSTEM_PROMPT = """You are the mandatory NORMALIZE_INPUT stage for a puzzle agent.
Return one valid JSON object only (no Markdown fences or surrounding prose). Classify kind as sudoku, nonogram, rule_puzzle, or general. Preserve all supplied clues.
The JSON object must use this envelope shape: {"kind":"general","title":"...","confidence":0.9,"warnings":[],"canonical":{"text":"..."}}. Replace the example values with the actual classification and faithfully transcribed puzzle.
For sudoku, canonical must contain size, grid using null for blanks, and optional symbols/regions/box shape.
For an ordinary 9×9 Sudoku image, omit symbols (the default is integer 1 through 9), return exactly 9 rows of 9 cells, use JSON integers 1..9 for printed clues and null for blanks. Never use strings, 0, empty strings, or dots for cells. Read only the large printed digits inside the board: ignore dates, timers, titles, number pads, pencil buttons, and other interface controls. Do not fill inferred answers. Recheck every row and column against the image before returning.
For a black-and-white nonogram, canonical must contain row_clues and column_clues as arrays of positive-integer arrays; use [] for an empty line. Read row clues left-to-right, one horizontal clue group per grid row. Read column clues top-to-bottom, one vertical clue stack per grid column; keep the printed order within each stack. Count the grid rows and columns before transcribing, and return exactly one clue array for each. Recheck that the sum of all row clue numbers equals the sum of all column clue numbers; if the image is ambiguous, report that in warnings instead of inventing clues. It may contain a grid using null for unknown, 1 for filled, and 0 for empty.
Use rule_puzzle only when the puzzle has a finite set of explicit symbolic entities and a finite integer domain that can be represented in the required schema. Merely having written instructions, rules, or clues does not make a puzzle a rule_puzzle. For an unstructured word, cipher, or other ordinary puzzle, use general and preserve its full text.
For rule_puzzle, extract the supplied rules and board without solving. canonical must contain: rules [{id,text}], unique integer symbols, entities [{id,label,value,row?,column?}], clues [{id,text,entity_ids}], and optional display {type:"grid",rows,columns}. Infer symbols only from an explicit finite domain/range in the supplied rules; never return an empty symbols list for a rule_puzzle and never invent a domain. If no finite integer domain is stated, classify as general unless the user explicitly selected rule_puzzle. Use null for unknown entity values. Every clue must name the entities it affects. Do not design the solving method; method synthesis is a separate stage.
For general puzzles, canonical must contain text and may contain title/artifact_notes.
Always include title, confidence (0..1), warnings (array), kind, and canonical.
Never solve the puzzle in this stage."""


def _valid_symbols(value: Any, size: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == size
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
        and len(set(value)) == size
    )


def _repair_ordinary_sudoku_json(envelope: Any) -> None:
    """Repair only unambiguous JSON representation noise for ordinary 1..9 Sudoku."""
    if not isinstance(envelope, dict) or envelope.get("kind") != "sudoku":
        return
    canonical = envelope.get("canonical")
    if not isinstance(canonical, dict) or canonical.get("size") != 9:
        return

    standard_symbols = list(range(1, 10))
    raw_symbols = canonical.get("symbols")
    if _valid_symbols(raw_symbols, 9) and raw_symbols != standard_symbols:
        return  # A valid custom alphabet (for example 0..8) is not ordinary Sudoku.

    raw_grid = canonical.get("grid")
    if not isinstance(raw_grid, list) or len(raw_grid) != 9:
        return
    repaired_grid: list[list[int | None]] = []
    changed = False
    blank_markers = {"", "0", ".", "-", "_"}
    for raw_row in raw_grid:
        if not isinstance(raw_row, list) or len(raw_row) != 9:
            return
        row: list[int | None] = []
        for raw_value in raw_row:
            value = raw_value
            if isinstance(value, str):
                stripped = value.strip()
                if stripped in blank_markers:
                    value = None
                elif len(stripped) == 1 and stripped in "123456789":
                    value = int(stripped)
                else:
                    return
                changed = True
            elif value == 0 and not isinstance(value, bool):
                value = None
                changed = True
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value not in standard_symbols
            ):
                return
            row.append(value)
        repaired_grid.append(row)

    if raw_symbols is not None and raw_symbols != standard_symbols:
        canonical["symbols"] = standard_symbols
        changed = True
    if repaired_grid != raw_grid:
        canonical["grid"] = repaired_grid
        changed = True
    if changed and isinstance(envelope.get("warnings"), list):
        envelope["warnings"].append(
            "已自动修正常规 9×9 数独的无歧义 JSON 格式；请在确认页逐格核对盘面。"
        )


class DeepSeekNormalizer:
    def __init__(self, provider):
        self.provider = provider

    def normalize(
        self,
        *,
        text: str = "",
        image: bytes | None = None,
        image_mime: str | None = None,
        preferred_kind: str | None = None,
    ) -> dict[str, Any]:
        if preferred_kind not in {None, "sudoku", "nonogram", "rule_puzzle", "general"}:
            raise NormalizationError(
                "preferred_kind must be sudoku, nonogram, rule_puzzle, general, or null"
            )
        text = text.strip()
        if not text and image is None:
            raise NormalizationError("text or image is required")
        kind_instruction = (
            f"\n\n玩家明确选择题型：{preferred_kind}。必须按该类型规范化并返回相同的 kind。"
            if preferred_kind else ""
        )
        parts: list[dict[str, Any]] = [{
            "type": "text",
            "text": (text or "The puzzle is entirely in the attached image.") + kind_instruction,
        }]
        if image is not None:
            if image_mime not in {"image/png", "image/jpeg", "image/webp"}:
                raise NormalizationError("unsupported image MIME")
            encoded = base64.b64encode(image).decode("ascii")
            parts.append({"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{encoded}"}})
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": parts},
        ]
        try:
            content = self.provider.complete(messages)
            envelope = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            # DeepSeek JSON mode can occasionally produce malformed/empty output.
            # Retry once with an explicit format reminder; never salvage guessed JSON.
            retry_messages = [
                messages[0],
                {
                    "role": "system",
                    "content": (
                        "Your previous response could not be parsed. Return one valid JSON object only; "
                        "no Markdown fences or prose. Use the required envelope keys kind, title, "
                        "confidence, warnings, canonical. Example: "
                        '{"kind":"general","title":"...","confidence":0.9,"warnings":[],"canonical":{"text":"..."}}'
                    ),
                },
                messages[1],
            ]
            try:
                content = self.provider.complete(retry_messages)
                envelope = json.loads(content)
            except (json.JSONDecodeError, TypeError) as exc:
                raise NormalizationError(
                    "DeepSeek did not return valid JSON after one retry"
                ) from exc
        _repair_ordinary_sudoku_json(envelope)
        if not isinstance(envelope, dict):
            raise NormalizationError("normalized envelope must be a JSON object")
        if preferred_kind is not None and envelope["kind"] != preferred_kind:
            raise NormalizationError(
                f"Model kind {envelope['kind']} does not match selected kind {preferred_kind}"
            )
        if preferred_kind == "rule_puzzle":
            try:
                validate_source(envelope.get("canonical"))
            except RulePuzzleError as source_error:
                repair_messages = [
                    messages[0],
                    {
                        "role": "system",
                        "content": (
                            "The previous normalized Rule puzzle did not satisfy the source schema: "
                            f"{source_error}. Re-read the original submission and return one corrected "
                            "JSON envelope. Infer an integer symbols domain only when explicitly stated "
                            "in the rules; do not invent values, solve the puzzle, or omit any clues."
                        ),
                    },
                    messages[1],
                ]
                try:
                    repaired = json.loads(self.provider.complete(repair_messages))
                    if not isinstance(repaired, dict) or repaired.get("kind") != "rule_puzzle":
                        raise NormalizationError(
                            "DeepSeek schema repair did not return a Rule puzzle envelope"
                        )
                    validate_source(repaired.get("canonical"))
                    envelope = repaired
                except RulePuzzleError as repair_error:
                    if "symbols must contain" in str(repair_error):
                        raise NormalizationError(
                            "按规则推理题需要 1–16 个不重复的整数候选符号；"
                            "请在题目规则中写明有限数字范围后重试。"
                        ) from repair_error
                    raise NormalizationError(
                        f"invalid normalized Rule puzzle after one schema repair: {repair_error}"
                    ) from repair_error
                except (json.JSONDecodeError, TypeError) as repair_error:
                    raise NormalizationError(
                        "DeepSeek could not repair the Rule puzzle schema after one retry"
                    ) from repair_error
        if preferred_kind is None and envelope.get("kind") == "rule_puzzle":
            try:
                validate_source(envelope.get("canonical"))
            except RulePuzzleError as exc:
                # Auto-classification must not block ordinary text because the model
                # guessed a rule puzzle but failed to produce its executable source schema.
                # Preserve the complete original submission and let the general Agent reason.
                fallback_text = text or json.dumps(
                    {"title": envelope.get("title"), "canonical": envelope.get("canonical")},
                    ensure_ascii=False,
                )
                envelope["kind"] = "general"
                envelope["canonical"] = {"text": fallback_text}
                envelope.setdefault("warnings", []).append(
                    "模型曾尝试识别为按规则推理题，但规则/实体/数字域结构不完整；已保留原题并转入普通谜题 Agent。若希望使用规则题组件，请在提交前明确选择“按规则推理”。"
                )
        self._validate_envelope(envelope, allow_sudoku_conflicts=True)
        source_hasher = hashlib.sha256()
        source_hasher.update(text.encode("utf-8"))
        if image is not None:
            source_hasher.update(b"\0image\0")
            source_hasher.update(image)
        return {
            "source_hash": source_hasher.hexdigest(),
            "envelope_hash": canonical_hash(envelope),
            "envelope": envelope,
        }

    @staticmethod
    def _validate_sudoku_structure(canonical: dict[str, Any]) -> None:
        """Validate editable OCR output without requiring the clues to be conflict-free."""
        spec = validate_spec(canonical)
        grid = canonical.get("grid")
        if not isinstance(grid, list) or len(grid) != spec.size:
            raise ValueError("grid must contain size rows")
        allowed = set(spec.symbols)
        for row in grid:
            if not isinstance(row, list) or len(row) != spec.size:
                raise ValueError("every grid row must contain size cells")
            for value in row:
                if value is not None and (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value not in allowed
                ):
                    raise ValueError("grid values must be null or members of symbols")

    @staticmethod
    def _validate_envelope(
        envelope: Any, *, allow_sudoku_conflicts: bool = False,
    ) -> None:
        if not isinstance(envelope, dict) or envelope.get("kind") not in {
            "sudoku", "nonogram", "rule_puzzle", "general",
        }:
            raise NormalizationError(
                "normalized kind must be sudoku, nonogram, rule_puzzle, or general"
            )
        canonical = envelope.get("canonical")
        if not isinstance(canonical, dict):
            raise NormalizationError("normalized canonical input must be an object")
        confidence = envelope.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            raise NormalizationError("normalized confidence must be in 0..1")
        if not isinstance(envelope.get("warnings"), list):
            raise NormalizationError("normalized warnings must be an array")
        if envelope["kind"] == "sudoku":
            try:
                DeepSeekNormalizer._validate_sudoku_structure(canonical)
                try:
                    build_state(canonical)
                except ValueError as exc:
                    if not allow_sudoku_conflicts:
                        raise
                    envelope["warnings"].append(
                        f"识别出的数独存在冲突（{exc}）；请在表格中修正标红格后再确认。"
                    )
            except ValueError as exc:
                raise NormalizationError(f"invalid normalized Sudoku: {exc}") from exc
        elif envelope["kind"] == "nonogram":
            try:
                build_nonogram_state(canonical)
            except ValueError as exc:
                raise NormalizationError(f"invalid normalized Nonogram: {exc}") from exc
        elif envelope["kind"] == "rule_puzzle":
            try:
                validate_source(canonical)
            except RulePuzzleError as exc:
                if "symbols must contain" in str(exc):
                    raise NormalizationError(
                        "按规则推理题需要 1–16 个不重复的整数候选符号；请在题目规则中写明有限数字范围后重试。"
                    ) from exc
                raise NormalizationError(f"invalid normalized Rule puzzle: {exc}") from exc
        elif not isinstance(canonical.get("text"), str) or not canonical["text"].strip():
            raise NormalizationError("general canonical input requires non-empty text")
