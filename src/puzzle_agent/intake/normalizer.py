from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from puzzle_agent.paper_puzzle.components.sudoku import build_state

from .contracts import canonical_hash


class NormalizationError(ValueError):
    """DeepSeek normalization output is invalid or unsupported."""


_SYSTEM_PROMPT = """You are the mandatory NORMALIZE_INPUT stage for a puzzle agent.
Return one JSON object only. Classify kind as sudoku or general. Preserve all supplied clues.
For sudoku, canonical must contain size, grid using null for blanks, and optional symbols/regions/box shape.
For general puzzles, canonical must contain text and may contain title/artifact_notes.
Always include title, confidence (0..1), warnings (array), kind, and canonical.
Never solve the puzzle in this stage."""


class DeepSeekNormalizer:
    def __init__(self, provider):
        self.provider = provider

    def normalize(
        self,
        *,
        text: str = "",
        image: bytes | None = None,
        image_mime: str | None = None,
    ) -> dict[str, Any]:
        text = text.strip()
        if not text and image is None:
            raise NormalizationError("text or image is required")
        parts: list[dict[str, Any]] = [{
            "type": "text",
            "text": text or "The puzzle is entirely in the attached image.",
        }]
        if image is not None:
            if image_mime not in {"image/png", "image/jpeg", "image/webp"}:
                raise NormalizationError("unsupported image MIME")
            encoded = base64.b64encode(image).decode("ascii")
            parts.append({"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{encoded}"}})
        content = self.provider.complete([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": parts},
        ])
        try:
            envelope = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise NormalizationError("DeepSeek did not return valid JSON") from exc
        self._validate_envelope(envelope)
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
    def _validate_envelope(envelope: Any) -> None:
        if not isinstance(envelope, dict) or envelope.get("kind") not in {"sudoku", "general"}:
            raise NormalizationError("normalized kind must be sudoku or general")
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
                build_state(canonical)
            except ValueError as exc:
                raise NormalizationError(f"invalid normalized Sudoku: {exc}") from exc
        elif not isinstance(canonical.get("text"), str) or not canonical["text"].strip():
            raise NormalizationError("general canonical input requires non-empty text")
