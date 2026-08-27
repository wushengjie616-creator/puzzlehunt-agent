"""Load derived puzzle inputs without exposing evaluator oracles."""

import json
from pathlib import Path
import re
from typing import Any


_REQUIRED_FILES = ("input.json", "oracle.json", "rubric.json", "provenance.json")
_FORBIDDEN_INPUT_KEYS = {"answer", "solution", "oracle"}


def discover_cases(root: str | Path, suite: str = "dev") -> list[Path]:
    suite_root = Path(root) / suite
    if not suite_root.is_dir():
        return []
    return sorted(
        path for path in suite_root.iterdir()
        if path.is_dir() and all((path / name).is_file() for name in _REQUIRED_FILES)
    )


def load_runtime_input(case_dir: str | Path) -> dict[str, Any]:
    data = _read_json(Path(case_dir) / "input.json")
    if not isinstance(data, dict):
        raise ValueError("benchmark input must be a JSON object")
    return data


def evaluate_case(case_dir: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    oracle = _read_json(Path(case_dir) / "oracle.json")
    actual = result.get("final_answer", result.get("answer"))
    correct = isinstance(actual, str) and _normalize(actual) == _normalize(oracle["answer"])
    return {"correct": correct, "score": 1.0 if correct else 0.0}


def validate_case(case_dir: str | Path) -> list[str]:
    case_dir = Path(case_dir)
    errors = [f"missing {name}" for name in _REQUIRED_FILES if not (case_dir / name).is_file()]
    if errors:
        return errors
    runtime_input = load_runtime_input(case_dir)
    oracle = _read_json(case_dir / "oracle.json")
    rubric = _read_json(case_dir / "rubric.json")
    provenance = _read_json(case_dir / "provenance.json")
    forbidden = _find_forbidden_keys(runtime_input)
    if forbidden:
        errors.append(f"forbidden runtime keys: {sorted(forbidden)}")
    answer = oracle.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        errors.append("oracle answer must be a non-empty string")
    elif answer.casefold() in json.dumps(runtime_input, ensure_ascii=False).casefold():
        errors.append("oracle answer leaks into runtime input")
    if not isinstance(rubric.get("milestones"), list) or not rubric["milestones"]:
        errors.append("rubric milestones must be a non-empty array")
    if not str(provenance.get("source_url", "")).startswith("https://ccbc16.cipherpuzzles.com/"):
        errors.append("provenance must cite the official CCBC16 site")
    if provenance.get("original_surface_and_data") is not True:
        errors.append("case must attest original surface and data")
    return errors


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_forbidden_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {str(key).casefold() for key in value if str(key).casefold() in _FORBIDDEN_INPUT_KEYS}
        for item in value.values():
            found.update(_find_forbidden_keys(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_find_forbidden_keys(item))
        return found
    return set()


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", value.casefold())
