"""Build a reusable evaluator-isolated CCBC16 text suite."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from typing import Any, Callable

from .benchmark import validate_case
from .hard_runner import convert_official_payload, load_nonmeta_manifest
from .ccbc16_script_surfaces import SCRIPT_SURFACE_URLS, extract_script_surface


JsonFetcher = Callable[[str], dict[str, Any]]
TextFetcher = Callable[[str], str]
_EMPHASIZED = re.compile(r"\*\*([^*\r\n]{1,100})\*\*|`([^`\r\n]{1,100})`")
_IMAGE_SRC = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in folded if character.isalnum())


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


def _verified_surface_transcription(
    puzzle_id: int,
    payload: dict[str, Any],
    override: Any,
) -> dict[str, Any]:
    if not isinstance(override, dict):
        raise ValueError(f"invalid surface transcription for puzzle {puzzle_id}")
    content = override.get("content")
    urls = override.get("artifact_urls")
    hashes = override.get("source_sha256")
    method = override.get("transcription_method")
    notes = override.get("fidelity_notes")
    missing = override.get("unrepresented_channels")
    if (
        not isinstance(content, str) or not content.strip()
        or not isinstance(urls, list) or not urls
        or not all(isinstance(item, str) and item.startswith(("http://", "https://")) for item in urls)
        or not isinstance(hashes, list) or len(hashes) != len(urls)
        or not all(isinstance(item, str) and _SHA256.fullmatch(item) for item in hashes)
        or method not in {"human-reviewed", "deterministic-plus-human-reviewed"}
        or not isinstance(notes, str) or not notes.strip()
        or not isinstance(missing, list) or missing
    ):
        raise ValueError(f"invalid surface transcription for puzzle {puzzle_id}")

    surface = "\n".join(
        str(payload.get(field) or "") for field in ("html", "content")
    )
    expected_urls = set(_IMAGE_SRC.findall(surface))
    image = payload.get("image")
    if isinstance(image, str) and image.strip():
        expected_urls.add(image.strip())
    tips = payload.get("tips")
    if isinstance(tips, list):
        for tip in tips:
            if isinstance(tip, dict) and "碎片" in str(tip.get("title") or ""):
                expected_urls.update(_IMAGE_SRC.findall(str(tip.get("content") or "")))
    if expected_urls and not expected_urls.issubset(set(urls)):
        raise ValueError(f"surface transcription omits an official artifact for puzzle {puzzle_id}")
    return dict(override)


def build_text_suite(
    *,
    manifest_path: str | Path,
    output_root: str | Path,
    fetch_json: JsonFetcher,
    checkpoint_overrides: dict[int, list[dict[str, str]]] | None = None,
    surface_overrides: dict[int, dict[str, Any]] | None = None,
    fetch_text: TextFetcher | None = None,
) -> dict[str, Any]:
    """Fetch official payloads and retain only self-contained textual surfaces."""

    output_root = Path(output_root)
    suite_root = output_root / "text"
    if suite_root.exists() and any(suite_root.iterdir()):
        raise ValueError("text suite output must be empty to avoid stale cases")
    entries = load_nonmeta_manifest(manifest_path)
    checkpoint_overrides = checkpoint_overrides or {}
    surface_overrides = surface_overrides or {}
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
        surface_transcription = None
        script_surface = None
        equivalent_copy_surface = (
            puzzle_id == 8
            and "方便复制版" in str(payload.get("html") or "")
        )
        if equivalent_copy_surface:
            reasons = [
                reason for reason in reasons
                if reason not in {"source-image", "source-interaction"}
            ]
            runtime_input["content"] = "\n".join(
                line for line in str(runtime_input.get("content") or "").splitlines()
                if not line.startswith("[IMAGE:")
            ).strip()
            if reasons:
                runtime_input["required_artifacts"] = reasons
            else:
                runtime_input.pop("required_artifacts", None)
        if puzzle_id in SCRIPT_SURFACE_URLS and fetch_text is not None:
            script_url = SCRIPT_SURFACE_URLS[puzzle_id]
            script_source = fetch_text(script_url)
            if not isinstance(script_source, str):
                raise ValueError(f"script fetcher returned non-text for puzzle {puzzle_id}")
            extracted = extract_script_surface(puzzle_id, script_source)
            original = str(runtime_input.get("content") or "")
            if original.startswith("[NO TEXTUAL SURFACE"):
                original = ""
            runtime_input["content"] = "\n\n".join(filter(None, [original, extracted]))
            reasons = [
                reason for reason in reasons
                if reason not in {"source-interaction", "empty-text-surface"}
            ]
            if reasons:
                runtime_input["required_artifacts"] = reasons
            else:
                runtime_input.pop("required_artifacts", None)
            script_surface = {
                "url": script_url,
                "sha256": sha256(script_source.encode("utf-8")).hexdigest(),
                "adapter": "official-public-clues-v1",
                "answer_fields_excluded": True,
            }
        if puzzle_id in surface_overrides:
            surface_transcription = _verified_surface_transcription(
                puzzle_id, payload, surface_overrides[puzzle_id]
            )
            reasons = [
                reason for reason in reasons
                if reason not in {
                    "source-image", "source-document", "source-media",
                    "source-fragments", "empty-text-surface",
                }
            ]
            original = str(runtime_input.get("content") or "")
            original_lines = [
                line for line in original.splitlines()
                if not line.startswith("[SOURCE ARTIFACT:")
                and not line.startswith("[NO TEXTUAL SURFACE")
            ]
            runtime_input["content"] = "\n\n".join(filter(None, [
                "\n".join(original_lines).strip(),
                "[HUMAN-REVIEWED STATIC ARTIFACT TRANSCRIPTION]\n"
                + surface_transcription["content"].strip(),
            ]))
            if reasons:
                runtime_input["required_artifacts"] = reasons
            else:
                runtime_input.pop("required_artifacts", None)
        if reasons:
            excluded.append({"puzzle_id": puzzle_id, "reasons": reasons})
            continue

        # Emphasis in prose is only a discovery aid: it frequently marks labels,
        # examples, or the final answer. Only reviewed overrides become oracle
        # checkpoints used for scoring.
        checkpoints: list[dict[str, str]] = []
        seen_checkpoints: set[str] = set()
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
        provenance = {
            "source_url": entry["url"],
            "source_data_url": entry["data_url"],
            "original_surface_and_data": True,
            "runtime_cache_only": True,
        }
        if surface_transcription is not None:
            provenance["surface_transcription"] = surface_transcription
        if script_surface is not None:
            provenance["script_surface"] = script_surface
        if equivalent_copy_surface:
            provenance["equivalent_copy_surface"] = True
        _write_json(case / "provenance.json", provenance)
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
