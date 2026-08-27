"""Persistent three-hour scheduler for the 24-hour evaluation window."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from .automation import run_watch_cycle
from .cycle_runner import run_cycle


def build_cycle_schedule(
    start: datetime,
    *,
    interval_hours: float = 3,
    duration_hours: float = 24,
) -> list[datetime]:
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("start must be timezone-aware")
    if interval_hours <= 0 or duration_hours <= 0 or interval_hours > duration_hours:
        raise ValueError("schedule hours must be positive and interval must fit duration")
    result: list[datetime] = []
    elapsed = interval_hours
    while elapsed <= duration_hours + 1e-9:
        result.append(start + timedelta(hours=elapsed))
        elapsed += interval_hours
    return result


def _write_state(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _clean(repository: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository,
        text=True,
        capture_output=True,
        check=True,
    )
    return not result.stdout.strip()


def _wait_until(due: datetime, stop: Path) -> bool:
    due_utc = due.astimezone(timezone.utc)
    while True:
        if stop.exists():
            return False
        remaining = (due_utc - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return True
        time.sleep(min(30.0, remaining))


def run_cycle_scheduler(
    repository: str | Path,
    *,
    start: datetime,
    cases_root: str | Path,
    runs_root: str | Path,
    provider_name: str = "deepseek",
    model: str = "deepseek-v4-pro",
    max_calls: int = 6,
    timeout_seconds: float = 3600,
    interval_hours: float = 3,
    duration_hours: float = 24,
) -> dict[str, Any]:
    repository = Path(repository).resolve()
    runtime = repository / ".puzzle-agent" / "automation"
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / "cycle-scheduler.lock"
    stop = runtime / "cycle-scheduler.stop"
    state_path = runtime / "cycle-scheduler-state.json"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
    except FileExistsError as exc:
        raise RuntimeError("cycle scheduler is already running") from exc

    schedule = build_cycle_schedule(
        start, interval_hours=interval_hours, duration_hours=duration_hours
    )
    state: dict[str, Any] = {
        "status": "running",
        "pid": os.getpid(),
        "start_at": start.isoformat(),
        "schedule": [item.isoformat() for item in schedule],
        "completed_cycles": [],
        "heartbeat_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "next_due": schedule[0].isoformat() if schedule else None,
    }
    if state_path.is_file():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if previous.get("start_at") == state["start_at"]:
            state["completed_cycles"] = previous.get("completed_cycles", [])
    _write_state(state_path, state)
    project_python = repository / ".venv" / "Scripts" / "python.exe"
    python = project_python if project_python.is_file() else Path(os.sys.executable)
    test_command = [str(python), "-m", "unittest", "discover", "-s", "tests", "-v"]

    try:
        completed_ids = {item["cycle_id"] for item in state["completed_cycles"]}
        for due in schedule:
            cycle_id = "cycle-" + due.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            if cycle_id in completed_ids:
                continue
            state["next_due"] = due.isoformat()
            state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _write_state(state_path, state)
            if not _wait_until(due, stop):
                state["status"] = "stopped"
                break

            while True:
                publish = run_watch_cycle(
                    repository,
                    test_command=test_command,
                    push=True,
                    validation_timeout_seconds=1800,
                )
                state["pre_cycle_publish"] = publish
                state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                _write_state(state_path, state)
                if publish["status"] in {"published", "no-changes"} and _clean(repository):
                    break
                if stop.exists():
                    state["status"] = "stopped"
                    break
                time.sleep(60)
            if state["status"] == "stopped":
                break

            attempt: dict[str, Any] = {
                "cycle_id": cycle_id,
                "scheduled_at": due.isoformat(),
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            try:
                manifest = run_cycle(
                    repository,
                    cases_root=cases_root,
                    runs_root=runs_root,
                    suite="v1",
                    provider_name=provider_name,
                    model=model,
                    max_calls=max_calls,
                    timeout_seconds=timeout_seconds,
                    cycle_id=cycle_id,
                    require_clean=True,
                    scheduled_at=due.isoformat(),
                )
                attempt["summary"] = manifest["summary"]
                if manifest["summary"]["correct"] == manifest["summary"]["total"]:
                    from .hard_runner import run_hard_once
                    try:
                        hard = run_hard_once(
                            repository,
                            manifest_path=repository / "research/ccbc16/nonmeta-manifest.json",
                            provider_name=provider_name,
                            model=model,
                            max_calls=max_calls,
                            timeout_seconds=timeout_seconds,
                            max_workers=5,
                        )
                        attempt["hard_suite"] = {
                            "status": hard["status"],
                            "summary": hard.get("summary"),
                        }
                    except RuntimeError as exc:
                        if "already been attempted" not in str(exc):
                            raise
                        attempt["hard_suite"] = {"status": "ALREADY_ATTEMPTED"}
                    except Exception as exc:
                        # The once-only marker is already persisted by the hard runner.
                        attempt["hard_suite"] = {
                            "status": "FAILED",
                            "error_type": type(exc).__name__,
                        }
            except Exception as exc:
                attempt["error_type"] = type(exc).__name__
            attempt["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            state["completed_cycles"].append(attempt)
            completed_ids.add(cycle_id)
            state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _write_state(state_path, state)
            state["post_cycle_publish"] = run_watch_cycle(
                repository,
                test_command=test_command,
                push=True,
                validation_timeout_seconds=1800,
            )
            _write_state(state_path, state)
        else:
            state["status"] = "completed"
        state["next_due"] = None
        state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_state(state_path, state)
        return state
    except Exception as exc:
        state["status"] = "failed"
        state["error_type"] = type(exc).__name__
        state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_state(state_path, state)
        raise
    finally:
        lock.unlink(missing_ok=True)


def scheduler_status(repository: str | Path) -> dict[str, Any]:
    runtime = Path(repository).resolve() / ".puzzle-agent" / "automation"
    state_path = runtime / "cycle-scheduler-state.json"
    if not state_path.exists():
        return {"status": "not-running"}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") == "running" and not (runtime / "cycle-scheduler.lock").exists():
        state["status"] = "stale"
    return state


def request_scheduler_stop(repository: str | Path) -> dict[str, str]:
    runtime = Path(repository).resolve() / ".puzzle-agent" / "automation"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "cycle-scheduler.stop").write_text("stop\n", encoding="ascii")
    return {"status": "stop-requested"}
