"""Load derived puzzle inputs without exposing evaluator oracles."""

import json
from pathlib import Path
import re
import unicodedata
from typing import Any


_REQUIRED_FILES = ("input.json", "oracle.json", "rubric.json", "provenance.json")
_FORBIDDEN_INPUT_KEYS = {"answer", "solution", "oracle"}
_V2_FLAVOR_LEAK = re.compile(
    r"(?i)caesar|atbash|a1z26|morse|vigen[eè]re|rail\s*fence|reverse|interleave|"
    r"凯撒|埃特巴什|摩斯|维吉尼亚|栅栏|倒序|反转|交错|取第|索引|首字|尾字|行号"
)


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


def evaluate_reasoning_state(state: dict[str, Any]) -> dict[str, Any]:
    """Score auditable process evidence separately from the submitted answer."""

    associations = state.get("association_candidates", [])
    hypotheses = state.get("hypotheses", [])
    checks = state.get("verification_checks", {})
    criteria = {
        "association_beam": isinstance(associations, list) and len(associations) >= 3,
        "falsifiable_bridges": isinstance(associations, list) and len(associations) >= 3
        and all(
            isinstance(item, dict)
            and len(item.get("signal_ids", [])) >= 2
            and bool(item.get("prediction"))
            and bool(item.get("falsifier"))
            for item in associations
        ),
        "competing_hypotheses": isinstance(hypotheses, list) and len(hypotheses) >= 2
        and all(
            isinstance(item, dict)
            and bool(item.get("prediction"))
            and bool(item.get("falsifier"))
            for item in hypotheses
        ),
        "experiment_and_evidence": (
            bool(state.get("attempts")) or state.get("plan") == []
        ) and bool(state.get("evidence")),
        "intermediate_materialized": bool(state.get("validated_intermediate_answers"))
        and bool(state.get("intermediate_validation", {}).get("passed")),
        "coverage_audited": state.get("unused_elements") == []
        and isinstance(checks, dict)
        and bool(checks)
        and all(checks.values()),
    }
    passed = sum(criteria.values())
    return {
        "reasoning_pass": passed == len(criteria),
        "score": passed / len(criteria),
        "passed_checks": passed,
        "total_checks": len(criteria),
        "checks": criteria,
    }


def evaluate_intermediate_case(
    case_dir: str | Path, state: dict[str, Any]
) -> dict[str, Any]:
    oracle = _read_json(Path(case_dir) / "oracle.json")
    checkpoints = oracle.get("intermediate_answers", [])
    expected_groups: list[set[str]] = []
    for item in checkpoints:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            continue
        values = [item["value"]]
        aliases = item.get("aliases", [])
        if isinstance(aliases, list):
            values.extend(alias for alias in aliases if isinstance(alias, str))
        normalized = {_normalize(value) for value in values if _normalize(value)}
        if normalized:
            expected_groups.append(normalized)
    actual = state.get("validated_intermediate_answers", [])
    actual_values = {
        _normalize(item["value"])
        for item in actual
        if isinstance(item, dict) and isinstance(item.get("value"), str)
        and _normalize(item["value"])
    }
    matched = sum(
        any(
            expected_value == actual_value
            or expected_value in actual_value
            or actual_value in expected_value
            for expected_value in group
            for actual_value in actual_values
        )
        for group in expected_groups
    )
    expected = len(expected_groups)
    return {
        "applicable": expected > 0,
        "pass": expected > 0 and matched == expected,
        "matched": matched,
        "expected": expected,
        "submitted": len(actual_values),
        "score": matched / expected if expected else 0.0,
    }


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
    sources = provenance.get("source_urls")
    if sources is None:
        sources = [provenance.get("source_url", "")]
    if not isinstance(sources, list) or not sources or not all(
        isinstance(url, str) and (
            url.startswith("https://ccbc16.cipherpuzzles.com/")
            or url.startswith("https://github.com/cipherpuzzles/CCBCArchive")
            or url.startswith("https://static.ccbcarchive.com/")
        )
        for url in sources
    ):
        errors.append("provenance must cite an official CCBC archive source")
    if provenance.get("original_surface_and_data") is not True:
        errors.append("case must attest original surface and data")
    if case_dir.parent.name == "v2":
        errors.extend(_validate_v2_reasoning_contract(runtime_input, rubric))
    return errors


def _validate_v2_reasoning_contract(
    runtime_input: dict[str, Any], rubric: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    flavor = str(runtime_input.get("flavor_text", ""))
    leak_level = rubric.get("flavor_leak_level")
    if not isinstance(leak_level, int) or isinstance(leak_level, bool) or leak_level not in {0, 1}:
        errors.append("v2 flavor leaks beyond allowed L0-L1")
    if _V2_FLAVOR_LEAK.search(flavor):
        errors.append("v2 flavor leaks an operator, parameter, or extraction instruction")
    if rubric.get("flavor_only_solvable") is not False:
        errors.append("v2 flavor-only solvability must be false")
    milestones = rubric.get("milestones", [])
    if not isinstance(milestones, list) or len(milestones) < 3:
        errors.append("v2 requires at least three reasoning milestones")
    signals = rubric.get("required_signals", [])
    if not isinstance(signals, list) or len(signals) < 2:
        errors.append("v2 requires at least two independent signals")
    decoys = rubric.get("decoys", [])
    if not isinstance(decoys, list) or len(decoys) < 2 or not all(
        isinstance(item, dict)
        and isinstance(item.get("hypothesis"), str)
        and isinstance(item.get("falsifier"), str)
        and item["hypothesis"].strip()
        and item["falsifier"].strip()
        for item in decoys
    ):
        errors.append("v2 requires two decoys with explicit falsifiers")
    for field in ("checkpoints", "coverage_ledger", "shortcut_red_team"):
        value = rubric.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"v2 {field} must be a non-empty array")
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
    folded = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in folded if character.isalnum())
