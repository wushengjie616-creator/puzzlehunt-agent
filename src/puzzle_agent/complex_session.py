"""Persistent complex puzzle session service."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from threading import Lock
from typing import Any
import uuid

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .complex_domain import new_puzzle_state
from .complex_graph import build_puzzle_graph


_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")
_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class _UnavailableProvider:
    def complete(self, messages):
        raise RuntimeError("A provider is required to advance this session")


class _CancellationRequested(RuntimeError):
    pass


class _CancellableProvider:
    def __init__(self, provider, stop_marker: Path):
        self.provider = provider
        self.stop_marker = stop_marker

    def complete(self, messages):
        if self.stop_marker.is_file():
            raise _CancellationRequested("Player requested cancellation")
        try:
            result = self.provider.complete(messages)
        except Exception as exc:
            if self.stop_marker.is_file():
                raise _CancellationRequested("Player requested cancellation") from exc
            raise
        if self.stop_marker.is_file():
            raise _CancellationRequested("Player requested cancellation")
        return result


class SessionManager:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self._run_lock = Lock()
        self._running: set[str] = set()

    def create(
        self,
        puzzle,
        *,
        max_calls: int = 8,
        required_artifacts=(),
        artifacts=None,
    ) -> str:
        state = new_puzzle_state(
            puzzle,
            max_calls=max_calls,
            required_artifacts=tuple(required_artifacts),
            artifacts=artifacts,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        session_id = uuid.uuid4().hex
        session_dir = self.root / session_id
        session_dir.mkdir()
        (session_dir / "artifacts").mkdir()
        self._write_json(session_dir / "puzzle.json", {
            "session_id": session_id,
            "initial_state": state,
        })
        self._append_event(session_id, "session_created", {"max_calls": max_calls})
        return session_id

    def run(self, session_id: str, provider) -> dict[str, Any]:
        session_dir = self._session_dir(session_id)
        stop_marker = session_dir / "stop.json"
        with self._run_lock:
            if session_id in self._running:
                raise ValueError("Session is already running")
            if stop_marker.is_file():
                return self._cancelled_state(session_id)
            self._running.add(session_id)
        try:
            cancellable = _CancellableProvider(provider, stop_marker)
            try:
                with self._open_graph(session_id, cancellable, step_mode=False) as (graph, config):
                    snapshot = graph.get_state(config)
                    if snapshot.values and not snapshot.next:
                        return dict(snapshot.values)
                    graph_input = None if snapshot.values else self._load_initial(session_id)
                    graph.invoke(graph_input, config)
                    result = dict(graph.get_state(config).values)
            except _CancellationRequested:
                result = self._mark_cancelled(session_id)
                self._append_event(session_id, "session_cancelled", self._state_summary(result))
                return result
            self._append_event(session_id, "session_run", self._state_summary(result))
            return result
        finally:
            with self._run_lock:
                self._running.discard(session_id)

    def request_stop(self, session_id: str) -> dict[str, Any]:
        session_dir = self._session_dir(session_id)
        with self._run_lock:
            if session_id not in self._running:
                raise ValueError("Session is not running")
            marker = session_dir / "stop.json"
            if marker.is_file():
                return json.loads(marker.read_text(encoding="utf-8"))
            requested = {
                "session_id": session_id,
                "status": "STOP_REQUESTED",
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_json(marker, requested)
        self._append_event(session_id, "session_stop_requested", {})
        return requested

    def step(self, session_id: str, provider) -> dict[str, Any]:
        with self._open_graph(session_id, provider, step_mode=True) as (graph, config):
            snapshot = graph.get_state(config)
            if snapshot.values and not snapshot.next:
                return dict(snapshot.values)
            graph_input = None if snapshot.values else self._load_initial(session_id)
            graph.invoke(graph_input, config)
            result = dict(graph.get_state(config).values)
        self._append_event(session_id, "session_step", self._state_summary(result))
        return result

    def resume(self, session_id: str, provider, response: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise ValueError("Resume response must be a JSON object")
        with self._open_graph(session_id, provider, step_mode=False) as (graph, config):
            snapshot = graph.get_state(config)
            if not snapshot.interrupts:
                raise ValueError("Session is not waiting for input")
            self._persist_artifacts(session_id, response)
            graph.invoke(Command(resume=response), config)
            result = dict(graph.get_state(config).values)
        self._append_event(session_id, "artifact_resumed", {
            "artifact_names": sorted(response),
            **self._state_summary(result),
        })
        return result

    def status(self, session_id: str) -> dict[str, Any]:
        with self._open_graph(session_id, _UnavailableProvider()) as (graph, config):
            snapshot = graph.get_state(config)
            state = dict(snapshot.values) if snapshot.values else self._load_initial(session_id)
        marker = self._session_dir(session_id) / "stop.json"
        return self._cancelled_overlay(state, marker) if marker.is_file() else state

    def history(self, session_id: str) -> list[dict[str, Any]]:
        with self._open_graph(session_id, _UnavailableProvider()) as (graph, config):
            return [
                {
                    "checkpoint_id": snapshot.config["configurable"].get("checkpoint_id"),
                    "created_at": snapshot.created_at,
                    "next": list(snapshot.next),
                    "values": dict(snapshot.values),
                }
                for snapshot in graph.get_state_history(config)
            ]

    def branch(self, session_id: str, checkpoint_id: str) -> str:
        selected = next(
            (item for item in self.history(session_id) if item["checkpoint_id"] == checkpoint_id),
            None,
        )
        if selected is None:
            raise ValueError(f"Unknown checkpoint: {checkpoint_id}")
        state = json.loads(json.dumps(selected["values"], ensure_ascii=False))
        new_id = uuid.uuid4().hex
        session_dir = self.root / new_id
        session_dir.mkdir(parents=True)
        (session_dir / "artifacts").mkdir()
        self._write_json(session_dir / "puzzle.json", {
            "session_id": new_id,
            "branched_from": {"session_id": session_id, "checkpoint_id": checkpoint_id},
            "initial_state": state,
        })
        last_node = state.get("last_node")
        if isinstance(last_node, str) and last_node:
            with self._open_graph(new_id, _UnavailableProvider()) as (graph, config):
                graph.update_state(config, state, as_node=last_node)
                seeded = graph.get_state(config)
                if tuple(seeded.next) != tuple(selected["next"]):
                    raise ValueError(
                        "Selected checkpoint cursor could not be reproduced in the branch"
                    )
        self._append_event(new_id, "session_branched", {
            "source_session_id": session_id,
            "checkpoint_id": checkpoint_id,
            "next": selected["next"],
        })
        return new_id

    def finalize(self, session_id: str) -> dict[str, Any]:
        state = self.status(session_id)
        if state.get("status") != "SOLVED" or not state.get("final_answer"):
            raise ValueError("Only a SOLVED session can be finalized")
        result = {
            "session_id": session_id,
            "status": "SOLVED",
            "answer": state["final_answer"],
            "calls_used": state["budget"]["calls_used"],
            "evidence_count": len(state.get("evidence", [])),
        }
        self._write_json(self._session_dir(session_id) / "final.json", result)
        self._append_event(session_id, "session_finalized", {
            "calls_used": result["calls_used"],
            "evidence_count": result["evidence_count"],
        })
        return result

    def _session_dir(self, session_id: str) -> Path:
        if not _SESSION_ID.fullmatch(session_id):
            raise ValueError("Invalid session id")
        session_dir = (self.root / session_id).resolve()
        if session_dir.parent != self.root or not session_dir.is_dir():
            raise ValueError(f"Unknown session: {session_id}")
        return session_dir

    def _load_initial(self, session_id: str) -> dict[str, Any]:
        path = self._session_dir(session_id) / "puzzle.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["initial_state"]

    def _cancelled_state(self, session_id: str) -> dict[str, Any]:
        with self._open_graph(session_id, _UnavailableProvider()) as (graph, config):
            snapshot = graph.get_state(config)
            state = dict(snapshot.values) if snapshot.values else self._load_initial(session_id)
        return self._cancelled_overlay(state, self._session_dir(session_id) / "stop.json")

    @staticmethod
    def _cancelled_overlay(state: dict[str, Any], marker: Path) -> dict[str, Any]:
        cancellation = json.loads(marker.read_text(encoding="utf-8"))
        result = dict(state)
        result.update({
            "status": cancellation["status"],
            "stage": "CANCELLED" if cancellation["status"] == "CANCELLED" else result.get("stage"),
            "next_node": None if cancellation["status"] == "CANCELLED" else result.get("next_node"),
            "cancellation": cancellation,
        })
        return result

    def _mark_cancelled(self, session_id: str) -> dict[str, Any]:
        marker = self._session_dir(session_id) / "stop.json"
        requested = json.loads(marker.read_text(encoding="utf-8"))
        requested.update({
            "status": "CANCELLED",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        })
        self._write_json(marker, requested)
        return self._cancelled_state(session_id)

    def _open_graph(self, session_id: str, provider, step_mode: bool = False):
        session_dir = self._session_dir(session_id)
        connection = sqlite3.connect(session_dir / "checkpoint.sqlite", check_same_thread=False)
        saver = SqliteSaver(connection)
        graph = build_puzzle_graph(provider, checkpointer=saver, step_mode=step_mode)
        config = {"configurable": {"thread_id": session_id}}

        class GraphContext:
            def __enter__(self):
                return graph, config

            def __exit__(self, exc_type, exc, traceback):
                connection.close()
                return False

        return GraphContext()

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _persist_artifacts(self, session_id: str, artifacts: dict[str, Any]) -> None:
        artifact_dir = self._session_dir(session_id) / "artifacts"
        for name, value in artifacts.items():
            if not isinstance(name, str) or not _ARTIFACT_NAME.fullmatch(name):
                raise ValueError(f"Invalid artifact name: {name!r}")
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
            path = artifact_dir / f"{name}.txt"
            temporary = path.with_suffix(".txt.tmp")
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)

    def _append_event(self, session_id: str, event_type: str, details: dict[str, Any]) -> None:
        event = {
            "at": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "details": details,
        }
        path = self._session_dir(session_id) / "events.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    @staticmethod
    def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": state.get("status"),
            "stage": state.get("stage"),
            "calls_used": state.get("budget", {}).get("calls_used", 0),
        }
