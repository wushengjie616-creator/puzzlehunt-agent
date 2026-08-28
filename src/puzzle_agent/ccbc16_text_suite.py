"""Build a reusable evaluator-isolated CCBC16 text suite."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Callable

from .benchmark import validate_case
from .hard_runner import convert_official_payload, load_nonmeta_manifest


JsonFetcher = Callable[[str], dict[str, Any]]
_EMPHASIZED = re.compile(r"\*\*([^*\r\n]{1,100})\*\*|`([^`\r\n]{1,100})`")


def _normalized(value: str) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", value.casefold())


def extract_solution_checkpoints(solution: str, final_answer: str) -> list[dict[str, str]]:
    """Extract explicitly emphasized carrier values without exposing solution prose."""

    if not isinstance(solution, str):
        return []
    final = _normalized(final_answer)
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for match in _EMPHASIZED.finditer(solution):
        bold, code = match.groups()
        value = (bold if bold is not None else code).strip()
        normalized = _normalized(value)
        if (
            not normalized
            or normalized == final
            or normalized in seen
            or len(value) > 80
            or value.startswith(("http://", "https://"))
        ):
            continue
        seen.add(normalized)
        result.append({
            "value": value,
            "source": "official-solution-emphasis",
        })
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def build_text_suite(
    *,
    manifest_path: str | Path,
    output_root: str | Path,
    fetch_json: JsonFetcher,
    checkpoint_overrides: dict[int, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Fetch official payloads and retain only self-contained textual surfaces."""

    output_root = Path(output_root)
    suite_root = output_root / "text"
    if suite_root.exists() and any(suite_root.iterdir()):
        raise ValueError("text suite output must be empty to avoid stale cases")
    entries = load_nonmeta_manifest(manifest_path)
    checkpoint_overrides = checkpoint_overrides or {}
    included_ids: list[int] = []
    excluded: list[dict[str, Any]] = []
    for entry in entries:
        puzzle_id = entry["puzzle_id"]
        payload = fetch_json(entry["data_url"])
        converted = convert_official_payload(payload, entry["data_url"])
        runtime_input = converted["input"]
        reasons = list(runtime_input.get("required_artifacts", []))
        if str(runtime_input.get("content", "")).startswith("[NO TEXTUAL SURFACE"):
            reasons.append("empty-text-surface")
        if reasons:
            excluded.append({"puzzle_id": puzzle_id, "reasons": reasons})
            continue

        solution = payload.get("analysis") or payload.get("solution") or ""
        checkpoints = extract_solution_checkpoints(
            solution, converted["oracle"]["answer"]
        )
        seen_checkpoints = {_normalized(item["value"]) for item in checkpoints}
        for item in checkpoint_overrides.get(puzzle_id, []):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("value"), str)
                or not isinstance(item.get("source"), str)
            ):
                raise ValueError(f"invalid checkpoint override for puzzle {puzzle_id}")
            normalized = _normalized(item["value"])
            if normalized and normalized != _normalized(converted["oracle"]["answer"]) and normalized not in seen_checkpoints:
                checkpoints.append(dict(item))
                seen_checkpoints.add(normalized)
        oracle = {
            "answer": converted["oracle"]["answer"],
            "intermediate_answers": checkpoints,
        }
        case = suite_root / f"ccbc16-{puzzle_id:03d}"
        _write_json(case / "input.json", runtime_input)
        _write_json(case / "oracle.json", oracle)
        _write_json(case / "rubric.json", {
            "milestones": [
                "produce evidence-backed intermediate carriers",
                "complete the final extraction",
            ],
            "intermediate_checkpoint_count": len(oracle["intermediate_answers"]),
        })
        _write_json(case / "provenance.json", {
            "source_url": entry["url"],
            "source_data_url": entry["data_url"],
            "original_surface_and_data": True,
            "runtime_cache_only": True,
        })
        errors = validate_case(case)
        if errors:
            raise ValueError(f"generated case {puzzle_id} is invalid: {errors}")
        included_ids.append(puzzle_id)

    report = {
        "schema_version": 1,
        "source_total": len(entries),
        "included_count": len(included_ids),
        "included_ids": included_ids,
        "excluded": excluded,
    }
    _write_json(output_root / "suite-manifest.json", report)
    return report
