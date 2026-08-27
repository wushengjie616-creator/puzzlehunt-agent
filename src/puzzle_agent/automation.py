"""Guarded Git publishing primitives for long-running local automation."""

from __future__ import annotations

import re
import subprocess
import json
import os
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence


class UnsafePublishError(RuntimeError):
    """Raised when a repository cannot be published without risking data leakage."""


_ALLOWLIST = (
    ".agents",
    ".env.example",
    ".gitignore",
    ".haiknow.yml",
    "README.md",
    "benchmarks",
    "examples",
    "haiknow-doc",
    "pyproject.toml",
    "research",
    "scripts",
    "src",
    "tests",
)

_SECRET_PATTERNS = (
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(rb"DEEPSEEK_API_KEY\s*=\s*(?!replace-with-|your-|<|\$\{|\{\{)[^\s\"']{12,}"),
)


def _git(root: Path, arguments: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise UnsafePublishError(message or f"git {' '.join(arguments)} failed")
    return result


def _staged_paths(root: Path) -> list[str]:
    output = _git(root, ["diff", "--cached", "--name-only", "-z"]).stdout
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def _unstage_allowlist(root: Path) -> None:
    _git(root, ["reset", "--quiet", "HEAD", "--", *_ALLOWLIST], check=False)


def _assert_staged_content_safe(root: Path, paths: list[str]) -> None:
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized == ".env.local" or normalized.startswith(".puzzle-agent/"):
            raise UnsafePublishError(f"forbidden runtime path staged: {path}")
        blob = _git(root, ["show", f":{path}"], check=False)
        if blob.returncode:
            continue
        if any(pattern.search(blob.stdout) for pattern in _SECRET_PATTERNS):
            raise UnsafePublishError(f"possible secret detected in staged file: {path}")


def _is_allowlisted(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized == item or normalized.startswith(f"{item}/") for item in _ALLOWLIST)


def _worktree_fingerprint(root: Path) -> str:
    listed = _git(
        root,
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    ).stdout
    digest = sha256()
    for raw_path in sorted(item for item in listed.split(b"\0") if item):
        path = raw_path.decode("utf-8")
        if not _is_allowlisted(path):
            continue
        digest.update(raw_path)
        digest.update(b"\0")
        file_path = root / path
        if file_path.is_file():
            digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run_watch_cycle(
    repository: str | Path,
    *,
    test_command: Sequence[str],
    push: bool = True,
    validation_timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """Validate one stable worktree snapshot, then publish it if unchanged."""

    root = Path(repository).resolve()
    if (root / ".puzzle-agent" / "automation" / "evaluation.lock").exists():
        return {"status": "deferred-evaluation", "pushed": False, "commit": None}
    before = _worktree_fingerprint(root)
    try:
        validation = subprocess.run(
            list(test_command),
            cwd=root,
            capture_output=True,
            check=False,
            timeout=validation_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {"status": "validation-timeout", "validation_exit_code": None}
    if validation.returncode:
        return {
            "status": "validation-failed",
            "validation_exit_code": validation.returncode,
        }
    after = _worktree_fingerprint(root)
    if after != before:
        return {"status": "changed-during-validation", "validation_exit_code": 0}
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return publish_once(
        root,
        message=f"automation: verified snapshot {timestamp}",
        push=push,
    )


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def watch_repository(
    repository: str | Path,
    *,
    test_command: Sequence[str],
    push: bool = True,
    interval_seconds: int = 300,
    validation_timeout_seconds: int = 1800,
    max_cycles: int | None = None,
) -> dict[str, Any]:
    """Continuously validate and publish stable snapshots with an audit heartbeat."""

    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")
    if max_cycles is not None and max_cycles < 1:
        raise ValueError("max_cycles must be positive when provided")
    root = Path(repository).resolve()
    runtime = root / ".puzzle-agent" / "automation"
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / "git-watch.lock"
    stop = runtime / "git-watch.stop"
    state_path = runtime / "git-watch-state.json"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
    except FileExistsError as exc:
        raise UnsafePublishError("git watcher is already running") from exc

    state: dict[str, Any] = {
        "status": "running",
        "pid": os.getpid(),
        "cycles_completed": 0,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "heartbeat_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_result": None,
    }
    _write_json_atomic(state_path, state)
    try:
        while True:
            if stop.exists():
                stop.unlink()
                state["status"] = "stopped"
                break
            result = run_watch_cycle(
                root,
                test_command=test_command,
                push=push,
                validation_timeout_seconds=validation_timeout_seconds,
            )
            state["cycles_completed"] += 1
            state["last_result"] = result
            state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _write_json_atomic(state_path, state)
            if max_cycles is not None and state["cycles_completed"] >= max_cycles:
                state["status"] = "completed"
                break
            deadline = time.monotonic() + interval_seconds
            while time.monotonic() < deadline:
                if stop.exists():
                    break
                time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
        state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_json_atomic(state_path, state)
        return state
    except Exception as exc:
        state["status"] = "failed"
        state["error_type"] = type(exc).__name__
        state["heartbeat_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_json_atomic(state_path, state)
        raise
    finally:
        lock.unlink(missing_ok=True)


def watch_status(repository: str | Path) -> dict[str, Any]:
    root = Path(repository).resolve()
    runtime = root / ".puzzle-agent" / "automation"
    state_path = runtime / "git-watch-state.json"
    if not state_path.is_file():
        return {"status": "not-running"}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") == "running" and not (runtime / "git-watch.lock").exists():
        state["status"] = "stale"
    return state


def request_watch_stop(repository: str | Path) -> dict[str, Any]:
    root = Path(repository).resolve()
    runtime = root / ".puzzle-agent" / "automation"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "git-watch.stop").write_text("stop\n", encoding="ascii")
    return {"status": "stop-requested"}


def publish_once(
    repository: str | Path,
    *,
    message: str,
    push: bool = True,
) -> dict[str, Any]:
    """Commit allowlisted changes and optionally push them after safety gates.

    The function refuses to mix with an existing staged transaction. Unknown root
    files are deliberately left untracked.
    """

    root = Path(repository).resolve()
    if not (root / ".git").is_dir():
        raise UnsafePublishError(f"not a Git worktree: {root}")
    if (root / ".puzzle-agent" / "automation" / "evaluation.lock").exists():
        return {"status": "deferred-evaluation", "pushed": False, "commit": None}

    staged_before = _git(root, ["diff", "--cached", "--quiet"], check=False)
    if staged_before.returncode != 0:
        raise UnsafePublishError("pre-existing staged changes require an explicit owner")
    ignored = _git(root, ["check-ignore", "--quiet", "--", ".env.local"], check=False)
    if ignored.returncode != 0:
        raise UnsafePublishError(".env.local must be ignored before publishing")

    existing_allowlist = [item for item in _ALLOWLIST if (root / item).exists()]
    _git(root, ["add", "-A", "--", *existing_allowlist])
    paths = _staged_paths(root)
    if not paths:
        return {"status": "no-changes", "pushed": False, "commit": None}
    try:
        whitespace = _git(root, ["diff", "--cached", "--check"], check=False)
        if whitespace.returncode:
            raise UnsafePublishError(whitespace.stdout.decode("utf-8", errors="replace").strip())
        _assert_staged_content_safe(root, paths)
    except Exception:
        _unstage_allowlist(root)
        raise

    _git(root, ["commit", "-m", message])
    commit = _git(root, ["rev-parse", "HEAD"]).stdout.decode("ascii").strip()
    pushed = False
    if push:
        remotes = _git(root, ["remote"]).stdout.decode("utf-8").split()
        if "origin" not in remotes:
            raise UnsafePublishError("origin remote is required for push")
        _git(root, ["push", "origin", "HEAD"])
        pushed = True
    return {"status": "published", "pushed": pushed, "commit": commit, "paths": paths}
