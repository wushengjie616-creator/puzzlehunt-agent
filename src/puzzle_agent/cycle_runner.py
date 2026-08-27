"""Timed, isolated evaluation primitives for recurring puzzle cycles."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Sequence

from .benchmark import discover_cases, evaluate_case, load_runtime_input, validate_case
from .domain import PuzzleInput


_GRAPH_NODES = (
    "intake",
    "artifact_inventory",
    "human_interrupt",
    "observe_classify",
    "hypothesize_plan",
    "tool_dispatch",
    "evaluate_evidence",
    "verify_answer",
)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        process.kill()


def execute_case_process(
    case_id: str,
    command: Sequence[str],
    output_path: str | Path,
    *,
    timeout_seconds: float = 3600,
) -> dict[str, Any]:
    """Run one case in a separate process and enforce a monotonic deadline."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    output_path = Path(output_path)
    started_wall = time.time()
    started_monotonic = time.monotonic()
    process = subprocess.Popen(list(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        stdout, stderr = process.communicate()
        duration_ms = round((time.monotonic() - started_monotonic) * 1000)
        return {
            "case_id": case_id,
            "status": "TIMEOUT",
            "timeout": True,
            "duration_ms": duration_ms,
            "started_at_epoch": started_wall,
            "exit_code": process.returncode,
        }

    duration_ms = round((time.monotonic() - started_monotonic) * 1000)
    if process.returncode != 0:
        return {
            "case_id": case_id,
            "status": "ERROR",
            "failure_class": "WORKER_ERROR",
            "timeout": False,
            "duration_ms": duration_ms,
            "started_at_epoch": started_wall,
            "exit_code": process.returncode,
            "stderr_sha256": _digest(stderr),
        }
    if not output_path.is_file():
        return {
            "case_id": case_id,
            "status": "ERROR",
            "failure_class": "MISSING_WORKER_RESULT",
            "timeout": False,
            "duration_ms": duration_ms,
            "started_at_epoch": started_wall,
            "exit_code": process.returncode,
            "stdout_sha256": _digest(stdout),
        }
    result = json.loads(output_path.read_text(encoding="utf-8"))
    return {
        "case_id": case_id,
        "status": result.get("status", "ERROR"),
        "timeout": False,
        "duration_ms": duration_ms,
        "started_at_epoch": started_wall,
        "exit_code": process.returncode,
        "worker_result": result,
    }


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def analyze_node_effects(traces: list[dict[str, Any]], *, correct: bool) -> list[dict[str, Any]]:
    """Summarize observable node effects without inferring private reasoning."""

    result: list[dict[str, Any]] = []
    for node in _GRAPH_NODES:
        matching = [item for item in traces if item.get("node") == node]
        written = sorted({field for item in matching for field in item.get("written_fields", [])})
        evidence = sorted({item_id for item in matching for item_id in item.get("new_evidence_ids", [])})
        activated = bool(matching)
        if not activated or not correct:
            usefulness = "UNASSESSABLE"
        elif node == "verify_answer" and written:
            usefulness = "ESSENTIAL"
        elif written or evidence:
            usefulness = "HELPFUL"
        else:
            usefulness = "NEUTRAL"
        result.append({
            "node": node,
            "expected_activation": node != "human_interrupt",
            "activated": activated,
            "activation_count": len(matching),
            "wall_time_ms": sum(int(item.get("wall_time_ms", 0)) for item in matching),
            "written_fields": written,
            "new_evidence_ids": evidence,
            "usefulness": usefulness,
            "issues": [],
        })
    return result


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _evidence_ids(state: dict[str, Any]) -> set[str]:
    return {
        str(item["id"])
        for item in state.get("evidence", [])
        if isinstance(item, dict) and "id" in item
    }


def run_case_worker(
    case_dir: str | Path,
    output_dir: str | Path,
    *,
    provider: Any,
    max_calls: int,
    max_steps: int = 32,
) -> dict[str, Any]:
    """Run a case by stepping the graph so every node has observable timing."""

    from .complex_session import SessionManager

    case_dir = Path(case_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime_input = load_runtime_input(case_dir)
    manager = SessionManager(output_dir / "sessions")
    session_id = manager.create(
        PuzzleInput.from_dict(runtime_input),
        max_calls=max_calls,
        required_artifacts=tuple(runtime_input.get("required_artifacts", [])),
        artifacts=runtime_input.get("artifacts", {}),
    )
    state = manager.status(session_id)
    trace: list[dict[str, Any]] = []
    terminal = {"SOLVED", "UNSOLVED", "EXHAUSTED", "BLOCKED_INPUT"}
    for _ in range(max_steps):
        before = state
        started = time.monotonic()
        state = manager.step(session_id, provider)
        elapsed_ms = round((time.monotonic() - started) * 1000)
        written_fields = sorted(
            key for key in set(before) | set(state) if before.get(key) != state.get(key)
        )
        trace.append({
            "node": state.get("last_node"),
            "stage": state.get("stage"),
            "wall_time_ms": elapsed_ms,
            "written_fields": written_fields,
            "new_evidence_ids": sorted(_evidence_ids(state) - _evidence_ids(before)),
            "calls_used": state.get("budget", {}).get("calls_used", 0),
        })
        if state.get("status") in terminal or state.get("next_node") is None:
            break
    else:
        raise RuntimeError(f"case exceeded max graph steps: {case_dir.name}")

    _json_write(output_dir / "state.json", state)
    result = {
        "schema_version": 1,
        "case_id": case_dir.name,
        "session_id": session_id,
        "status": state.get("status"),
        "final_answer": state.get("final_answer"),
        "calls_used": state.get("budget", {}).get("calls_used", 0),
        "trace": trace,
        "state_path": "state.json",
    }
    _json_write(output_dir / "worker-result.json", result)
    return result


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _cycle_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cycle(
    repository: str | Path,
    *,
    cases_root: str | Path,
    runs_root: str | Path,
    suite: str = "v1",
    provider_name: str = "deepseek",
    model: str = "deepseek-v4-pro",
    max_calls: int = 6,
    timeout_seconds: float = 3600,
    cycle_id: str | None = None,
    require_clean: bool = True,
    scheduled_at: str | None = None,
    expected_case_count: int = 5,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Run all cases concurrently against one frozen Git commit."""

    repository = Path(repository).resolve()
    cases_root = Path(cases_root).resolve()
    runs_root = Path(runs_root).resolve()
    cycle_id = cycle_id or _cycle_id_now()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", cycle_id):
        raise ValueError("cycle_id contains unsafe characters")
    if provider_name not in {"offline", "deepseek"}:
        raise ValueError("provider_name must be offline or deepseek")
    cases = discover_cases(cases_root, suite)
    if expected_case_count < 1:
        raise ValueError("expected_case_count must be positive")
    if len(cases) != expected_case_count or any(validate_case(case) for case in cases):
        raise ValueError(
            f"cycle suite must contain exactly {expected_case_count} valid isolated cases"
        )
    worker_count = max_workers if max_workers is not None else len(cases)
    if worker_count < 1:
        raise ValueError("max_workers must be positive")
    worker_count = min(worker_count, len(cases))
    dirty = bool(_git_output(repository, "status", "--porcelain"))
    if require_clean and dirty:
        raise ValueError("cycle requires a clean frozen Git worktree")

    runtime = repository / ".puzzle-agent" / "automation"
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / "evaluation.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, cycle_id.encode("ascii"))
        os.close(descriptor)
    except FileExistsError as exc:
        raise RuntimeError("an evaluation cycle is already running") from exc

    run_dir = runs_root / cycle_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
        started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        commit = _git_output(repository, "rev-parse", "HEAD")
        commands: dict[str, list[str]] = {}
        for case in cases:
            output_dir = run_dir / "cases" / case.name
            commands[case.name] = [
                sys.executable,
                "-m",
                "puzzle_agent",
                "cycle",
                "worker",
                "--case-dir",
                str(case),
                "--output-dir",
                str(output_dir),
                "--provider",
                provider_name,
                "--model",
                model,
                "--max-calls",
                str(max_calls),
            ]

        def execute(case: Path) -> dict[str, Any]:
            output = run_dir / "cases" / case.name / "worker-result.json"
            return execute_case_process(
                case.name,
                commands[case.name],
                output,
                timeout_seconds=timeout_seconds,
            )

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            process_results = list(executor.map(execute, cases))

        case_results: list[dict[str, Any]] = []
        for case, process_result in zip(cases, process_results):
            worker = process_result.get("worker_result")
            if worker:
                score = evaluate_case(case, {"final_answer": worker.get("final_answer")})
                correct = score["correct"]
                status = "SOLVED" if correct else (
                    "WRONG" if worker.get("final_answer") else worker.get("status", "ERROR")
                )
                trace = worker.get("trace", [])
                normalized_answer = worker.get("final_answer")
                calls_used = worker.get("calls_used", 0)
            else:
                correct = False
                status = process_result["status"]
                trace = []
                normalized_answer = None
                calls_used = 0
            node_report = analyze_node_effects(trace, correct=correct)
            case_output = run_dir / "cases" / case.name
            _json_write(case_output / "node-analysis.json", node_report)
            case_started = datetime.fromtimestamp(
                process_result["started_at_epoch"], tz=timezone.utc
            )
            case_deadline = case_started + timedelta(seconds=timeout_seconds)
            frozen = (
                case_started + timedelta(milliseconds=process_result["duration_ms"])
                if worker else None
            )
            case_results.append({
                "case_id": case.name,
                "started_at": case_started.isoformat(timespec="milliseconds"),
                "deadline_at": case_deadline.isoformat(timespec="milliseconds"),
                "final_answer_frozen_at": (
                    frozen.isoformat(timespec="milliseconds") if frozen else None
                ),
                "status": status,
                "failure_class": process_result.get("failure_class"),
                "timeout": process_result["timeout"],
                "duration_ms": process_result["duration_ms"],
                "normalized_answer": normalized_answer,
                "correct": correct,
                "rubric_score": 1.0 if correct else 0.0,
                "llm_calls": calls_used,
                "node_report_path": f"cases/{case.name}/node-analysis.json",
                "trace_path": f"cases/{case.name}/worker-result.json",
            })

        finished_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        summary = {
            "total": len(case_results),
            "correct": sum(item["correct"] for item in case_results),
            "wrong": sum(item["status"] == "WRONG" for item in case_results),
            "timeout": sum(item["status"] == "TIMEOUT" for item in case_results),
            "error": sum(item["status"] == "ERROR" for item in case_results),
        }
        manifest = {
            "schema_version": 1,
            "cycle_id": cycle_id,
            "scheduled_at": scheduled_at,
            "started_at": started_at,
            "finished_at": finished_at,
            "git_commit": commit,
            "dirty_worktree_at_start": dirty,
            "framework": {
                "prompt_hash": _file_hash(repository / "src" / "puzzle_agent" / "complex_graph.py"),
                "tool_registry_hash": _file_hash(repository / "src" / "puzzle_agent" / "tool_registry.py"),
                "dependency_hash": _file_hash(repository / "pyproject.toml"),
            },
            "provider": {"name": provider_name, "model": model, "max_calls": max_calls},
            "suite": suite,
            "timeout_seconds": timeout_seconds,
            "cases": case_results,
            "summary": summary,
        }
        _json_write(run_dir / "manifest.json", manifest)
        _write_cycle_analysis(run_dir / "analysis.md", manifest)
        return manifest
    finally:
        lock.unlink(missing_ok=True)


def _write_cycle_analysis(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        f"# Cycle {manifest['cycle_id']}",
        "",
        f"- Git commit: `{manifest['git_commit']}`",
        f"- Provider: `{manifest['provider']['name']}` / `{manifest['provider']['model']}`",
        f"- Result: {manifest['summary']['correct']}/{manifest['summary']['total']}",
        "",
        "| Case | Status | Time (ms) | Calls | Correct |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in manifest["cases"]:
        lines.append(
            f"| {item['case_id']} | {item['status']} | {item['duration_ms']} | "
            f"{item['llm_calls']} | {str(item['correct']).lower()} |"
        )
    lines.extend([
        "",
        "逐节点的激活、耗时、写入字段与可评估作用见每题 `node-analysis.json`。",
        "未答对时节点作用保持 `UNASSESSABLE`，避免把相关性误报为因果贡献。",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
