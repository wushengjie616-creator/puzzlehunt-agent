from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PuzzleInput:
    title: str = ""
    flavor_text: str = ""
    content: str = ""
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PuzzleInput":
        if not isinstance(data, dict):
            raise ValueError("Puzzle input must be a JSON object")
        values: dict[str, str | None] = {}
        for name in ("title", "flavor_text", "content", "notes"):
            value = data.get(name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
            values[name] = value
        return cls(
            title=values["title"] or "",
            flavor_text=values["flavor_text"] or "",
            content=values["content"] or "",
            notes=values["notes"],
        )

    def validate(self) -> None:
        if not any(part.strip() for part in (self.title, self.flavor_text, self.content, self.notes or "")):
            raise ValueError("Puzzle input is empty")


@dataclass(frozen=True)
class CipherCandidate:
    method: str
    source_segment: str
    output: str
    score: float
    parameters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolveResult:
    answer: str | None
    confidence: str
    reasoning_summary: tuple[str, ...] = ()
    key_evidence: tuple[str, ...] = ()
    methods_tried: tuple[str, ...] = ()
    alternatives: tuple[dict[str, Any], ...] = ()
    missing_information: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SolveResult":
        if not isinstance(data, dict):
            raise ValueError("Model response must be a JSON object")
        answer = data.get("answer")
        if answer is not None and not isinstance(answer, str):
            raise ValueError("answer must be a string or null")
        confidence = data.get("confidence", "low")
        if confidence not in {"low", "medium", "high"}:
            raise ValueError("confidence must be low, medium, or high")

        def strings(name: str) -> tuple[str, ...]:
            value = data.get(name, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{name} must be an array of strings")
            return tuple(value)

        alternatives = data.get("alternatives", [])
        if not isinstance(alternatives, list) or not all(isinstance(item, dict) for item in alternatives):
            raise ValueError("alternatives must be an array of objects")
        return cls(
            answer=answer,
            confidence=confidence,
            reasoning_summary=strings("reasoning_summary"),
            key_evidence=strings("key_evidence"),
            methods_tried=strings("methods_tried"),
            alternatives=tuple(alternatives),
            missing_information=strings("missing_information"),
        )
