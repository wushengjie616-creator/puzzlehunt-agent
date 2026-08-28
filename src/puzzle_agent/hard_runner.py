"""One-shot, redacted CCBC16 non-meta evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
from typing import Any, Callable
from urllib.request import Request, urlopen

from .cycle_runner import run_cycle


JsonFetcher = Callable[[str], dict[str, Any]]


class _TextConverter(HTMLParser):
    _BREAK_TAGS = {"br", "div", "p", "li", "tr", "table", "section", "h1", "h2", "h3"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BREAK_TAGS:
            self.parts.append("\n")
        if tag == "img":
            values = dict(attrs)
            label = values.get("alt") or values.get("src") or "image"
            self.parts.append(f"[IMAGE: {label}]")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BREAK_TAGS or tag in {"td", "th"}:
            self.parts.append("\n" if tag in self._BREAK_TAGS else " | ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line).strip()


def _html_to_text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    parser = _TextConverter()
    parser.feed(value)
    parser.close()
    return parser.text()


def load_nonmeta_manifest(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("puzzles") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("non-meta manifest must contain a non-empty puzzles array")
    ids: list[int] = []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("puzzle_id"), int):
            raise ValueError("every manifest item must have an integer puzzle_id")
        if not str(item.get("data_url", "")).startswith("https://ccbc16.cipherpuzzles.com/"):
            raise ValueError("every manifest item must use an official data_url")
        ids.append(item["puzzle_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("non-meta manifest contains duplicate puzzle IDs")
    return entries


def convert_official_payload(payload: dict[str, Any], source_url: str) -> dict[str, Any]:
    """Separate a public puzzle surface from its parent-only oracle."""

    if not isinstance(payload, dict):
        raise ValueError("official payload must be an object")
    if payload.get("answer_type") != 0:
        raise ValueError("hard suite accepts only official non-meta answer_type=0 puzzles")
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("official payload has no usable answer")
    content_parts = [
        _html_to_text(payload.get("content")),
        _html_to_text(payload.get("extend_content")),
    ]
    image = payload.get("image")
    if isinstance(image, str) and image.strip():
        content_parts.append(f"[SOURCE ARTIFACT: {image.strip()}]")
    content = "\n\n".join(part for part in content_parts if part).strip()
    if not content:
        content = "[NO TEXTUAL SURFACE; source requires an interactive or visual artifact]"
    required_artifacts: list[str] = []
    if isinstance(image, str) and image.strip():
        required_artifacts.append("source-image")
    if isinstance(payload.get("script"), str) and payload["script"].strip():
        required_artifacts.append("source-interaction")
    runtime_input: dict[str, Any] = {
        "title": _html_to_text(payload.get("title")),
        "flavor_text": _html_to_text(payload.get("desc")),
        "content": content,
        "notes": (
            "CCBC16 official surface converted to text for a one-shot private evaluation. "
            f"Source data: {source_url}. Image/interactive placeholders are evidence, not invented data."
        ),
    }
    if required_artifacts:
        runtime_input["required_artifacts"] = required_artifacts
    return {
        "input": runtime_input,
        "oracle": {"answer": answer},
    }


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "puzzlehunt-agent/0.1 research evaluation"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _error_categories(cases: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in cases:
        if item.get("correct"):
            category = "CORRECT"
        elif item.get("timeout"):
            category = "TIMEOUT"
        elif item.get("failure_class"):
            category = str(item["failure_class"])
        elif item.get("status") == "WRONG":
            category = "WRONG_ANSWER"
        else:
            category = str(item.get("status") or "UNKNOWN")
        result[category] = result.get(category, 0) + 1
    return result


def run_hard_once(
    repository: str | Path,
    *,
    manifest_path: str | Path,
    provider_name: str = "deepseek",
    model: str = "deepseek-v4-pro",
    max_calls: int = 8,
    timeout_seconds: float = 3600,
    max_workers: int = 5,
    fetch_json: JsonFetcher = _fetch_json,
    cycle_executor: Callable[..., dict[str, Any]] = run_cycle,
) -> dict[str, Any]:
    """Attempt the official hard suite exactly once and persist only a redacted report."""

    repository = Path(repository).resolve()
    entries = load_nonmeta_manifest(manifest_path)
    report_path = repository / "benchmarks/cycles/hard/once-result.json"
    if report_path.exists():
        raise RuntimeError("CCBC16 hard suite has already been attempted")
    started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    _write_json(report_path, {
        "schema_version": 1,
        "status": "IN_PROGRESS",
        "started_at": started,
        "once_only": True,
        "planned_total": len(entries),
    })

    cache = repository / ".puzzle-agent/hard-cache"
    cases_root = cache / "cases"
    runs_root = cache / "runs"
    suite_root = cases_root / "hard"
    try:
        for entry in entries:
            puzzle_id = entry["puzzle_id"]
            payload = fetch_json(entry["data_url"])
            converted = convert_official_payload(payload, entry["data_url"])
            case = suite_root / f"ccbc16-{puzzle_id:03d}"
            _write_json(case / "input.json", converted["input"])
            _write_json(case / "oracle.json", converted["oracle"])
            _write_json(case / "rubric.json", {"milestones": ["official normalized answer"]})
            _write_json(case / "provenance.json", {
                "source_url": entry["url"],
                "original_surface_and_data": True,
                "transient_text_conversion": True,
            })
        manifest = cycle_executor(
            repository=repository,
            cases_root=cases_root,
            runs_root=runs_root,
            suite="hard",
            provider_name=provider_name,
            model=model,
            max_calls=max_calls,
            timeout_seconds=timeout_seconds,
            cycle_id="ccbc16-hard-once",
            require_clean=False,
            expected_case_count=len(entries),
            max_workers=max_workers,
        )
        redacted_cases = [{
            "puzzle_id": int(item["case_id"].rsplit("-", 1)[-1]),
            "status": item.get("status"),
            "correct": bool(item.get("correct")),
            "duration_ms": item.get("duration_ms"),
            "llm_calls": item.get("llm_calls"),
            "timeout": bool(item.get("timeout")),
            "failure_class": item.get("failure_class"),
        } for item in manifest["cases"]]
        report = {
            "schema_version": 1,
            "status": "COMPLETED",
            "once_only": True,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "git_commit": manifest.get("git_commit"),
            "summary": manifest["summary"],
            "error_categories": _error_categories(redacted_cases),
            "cases": redacted_cases,
            "copyright_boundary": "No puzzle surface, official answer, solution, or model answer is persisted.",
        }
        _write_json(report_path, report)
        return report
    except Exception as exc:
        failed = {
            "schema_version": 1,
            "status": "FAILED",
            "once_only": True,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "error_type": type(exc).__name__,
        }
        _write_json(report_path, failed)
        raise
    finally:
        if cache.exists():
            shutil.rmtree(cache)
