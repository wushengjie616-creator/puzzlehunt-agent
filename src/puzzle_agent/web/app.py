from __future__ import annotations

import base64
from copy import deepcopy
import os
from pathlib import Path
import secrets
from threading import Lock, Thread
from typing import Any
from urllib.parse import urlparse
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from puzzle_agent.config import load_env_local
from puzzle_agent.domain import PuzzleInput
from puzzle_agent.intake.contracts import ReceiptError, ReceiptSigner, canonical_hash
from puzzle_agent.intake.normalizer import DeepSeekNormalizer, NormalizationError
from puzzle_agent.intake.uploads import UploadError, validate_image_upload
from puzzle_agent.paper_puzzle.gateway import PaperPuzzleGateway
from puzzle_agent.providers.deepseek import DeepSeekConfig, DeepSeekProvider


_STATIC = Path(__file__).with_name("static")
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver", "::1"}


class _UnavailableNormalizer:
    def normalize(self, **kwargs):
        raise RuntimeError("DEEPSEEK_API_KEY is required for mandatory input normalization")


def _default_normalizer():
    load_env_local()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return _UnavailableNormalizer()
    provider = DeepSeekProvider(DeepSeekConfig(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-flash"),
        thinking="disabled",
        reasoning_effort="low",
        max_tokens=8192,
    ))
    return DeepSeekNormalizer(provider)


def _default_agent_provider():
    load_env_local()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return DeepSeekProvider(DeepSeekConfig(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    ))


def create_app(
    *,
    normalizer=None,
    agent_provider=None,
    receipt_secret: bytes | None = None,
    capability_token: str | None = None,
    sessions_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Puzzle Agent Local Web", docs_url=None, redoc_url=None)
    app.state.normalizer = normalizer or _default_normalizer()
    app.state.agent_provider = agent_provider or _default_agent_provider()
    app.state.signer = ReceiptSigner(receipt_secret or secrets.token_bytes(32))
    app.state.capability = capability_token or secrets.token_urlsafe(32)
    app.state.gateway = PaperPuzzleGateway()
    app.state.intakes: dict[str, dict[str, Any]] = {}
    app.state.sessions: dict[str, dict[str, Any]] = {}
    app.state.lock = Lock()
    app.state.sessions_root = (sessions_root or Path(".puzzle-agent/web-sessions")).resolve()
    app.state.complex_manager = None

    @app.middleware("http")
    async def local_write_guard(request: Request, call_next):
        host = request.headers.get("host", "").split(":", 1)[0].strip("[]").lower()
        if host not in _ALLOWED_HOSTS:
            return JSONResponse({"detail": "Host is not allowed in local mode"}, status_code=403)
        if request.method in _WRITE_METHODS and request.url.path.startswith("/api/"):
            if request.headers.get("x-puzzle-capability") != app.state.capability:
                return JSONResponse({"detail": "Missing or invalid local capability"}, status_code=403)
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return JSONResponse({"detail": "JSON requests are required"}, status_code=415)
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                origin_host = (parsed.hostname or "").lower()
                if parsed.scheme not in {"http", "https"} or origin_host != host:
                    return JSONResponse({"detail": "Cross-origin writes are forbidden"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'"
        return response

    @app.get("/")
    def home():
        return FileResponse(_STATIC / "index.html")

    @app.get("/static/{name}")
    def static_asset(name: str):
        if name not in {"app.js", "styles.css"}:
            raise HTTPException(404)
        return FileResponse(_STATIC / name)

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local"}

    @app.get("/api/bootstrap")
    def bootstrap():
        return {
            "login_required": False,
            "capability_token": app.state.capability,
            "catalog": app.state.gateway.catalog(),
            "normalization_required": True,
        }

    def add_event(record: dict[str, Any], event: str, detail: str) -> None:
        record["events"].append({"id": len(record["events"]) + 1, "event": event, "detail": detail})

    def run_normalization(intake_id: str, text: str, image: bytes | None, image_mime: str | None) -> None:
        record = app.state.intakes[intake_id]
        try:
            record["status"] = "NORMALIZING"
            add_event(record, "normalizing", "DeepSeek NORMALIZE_INPUT started")
            result = app.state.normalizer.normalize(text=text, image=image, image_mime=image_mime)
            record.update(result)
            record["status"] = "READY_FOR_CONFIRMATION"
            add_event(record, "ready", "Model output validated; user confirmation required")
        except Exception as exc:
            record["status"] = "FAILED"
            record["error"] = str(exc)
            add_event(record, "failed", "Normalization failed")

    @app.post("/api/intakes", status_code=202)
    async def create_intake(request: Request):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "JSON object required")
        text = body.get("text", "")
        if not isinstance(text, str) or len(text) > 50_000:
            raise HTTPException(400, "text must be at most 50000 characters")
        image_data = None
        image_mime = None
        image = body.get("image")
        if image is not None:
            if not isinstance(image, dict):
                raise HTTPException(400, "image must be an object")
            encoded = image.get("data_base64", "")
            if not isinstance(encoded, str) or len(encoded) > 15_000_000:
                raise HTTPException(413, "encoded image is too large")
            try:
                raw = base64.b64decode(encoded, validate=True)
                validated = validate_image_upload(
                    raw,
                    image.get("mime", ""),
                    filename=image.get("name", "upload"),
                )
            except (ValueError, UploadError) as exc:
                raise HTTPException(400, str(exc)) from exc
            image_data, image_mime = validated.data, validated.mime
        if not text.strip() and image_data is None:
            raise HTTPException(400, "text or image is required")
        intake_id = uuid.uuid4().hex
        record = {"intake_id": intake_id, "status": "QUEUED", "events": []}
        add_event(record, "queued", "Input accepted by local safety gate")
        app.state.intakes[intake_id] = record
        Thread(
            target=run_normalization,
            args=(intake_id, text, image_data, image_mime),
            daemon=True,
            name=f"normalize-{intake_id[:8]}",
        ).start()
        return {"intake_id": intake_id, "status": "QUEUED"}

    def get_intake_record(intake_id: str) -> dict[str, Any]:
        record = app.state.intakes.get(intake_id)
        if record is None:
            raise HTTPException(404, "Unknown intake")
        return record

    @app.get("/api/intakes/{intake_id}")
    def get_intake(intake_id: str):
        return deepcopy(get_intake_record(intake_id))

    @app.get("/api/intakes/{intake_id}/events")
    def get_intake_events(intake_id: str, after: int = 0):
        record = get_intake_record(intake_id)
        return {"events": [event for event in record["events"] if event["id"] > after]}

    @app.post("/api/intakes/{intake_id}/confirm")
    async def confirm_intake(intake_id: str, request: Request):
        record = get_intake_record(intake_id)
        if record["status"] != "READY_FOR_CONFIRMATION":
            raise HTTPException(409, "Intake is not ready for confirmation")
        body = await request.json()
        canonical = body.get("canonical") if isinstance(body, dict) else None
        envelope = deepcopy(record["envelope"])
        envelope["canonical"] = canonical
        try:
            DeepSeekNormalizer._validate_envelope(envelope)
        except NormalizationError as exc:
            raise HTTPException(422, str(exc)) from exc
        receipt = app.state.signer.issue(
            record["source_hash"], record["envelope_hash"], canonical_hash(canonical)
        )
        record["confirmed_canonical"] = canonical
        record["receipt"] = receipt
        record["status"] = "CONFIRMED"
        add_event(record, "confirmed", "Canonical input confirmed and receipt issued")
        return {"intake_id": intake_id, "receipt": receipt, "canonical_hash": canonical_hash(canonical)}

    @app.post("/api/sessions", status_code=201)
    async def create_session(request: Request):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "JSON object required")
        record = get_intake_record(str(body.get("intake_id", "")))
        canonical = body.get("canonical")
        try:
            app.state.signer.verify(
                str(body.get("receipt", "")), canonical=canonical,
                source_hash=record.get("source_hash", ""),
            )
        except ReceiptError as exc:
            raise HTTPException(403, str(exc)) from exc
        if canonical != record.get("confirmed_canonical"):
            raise HTTPException(403, "Canonical input is not the confirmed version")
        session_id = uuid.uuid4().hex
        kind = record["envelope"]["kind"]
        if kind == "sudoku":
            result = app.state.gateway.run({"kind": kind, "canonical": canonical})
            if result["status"] == "STALLED" and app.state.agent_provider is not None:
                try:
                    result["advisory"] = app.state.gateway.advise_stall(
                        result, app.state.agent_provider
                    )
                except (RuntimeError, ValueError) as exc:
                    result["advisory"] = {
                        "status": "UNVERIFIED_ADVISORY",
                        "message": f"Advisory unavailable: {exc}",
                    }
            session = {"session_id": session_id, "kind": kind, "status": result["status"], "result": result}
        else:
            from puzzle_agent.complex_session import SessionManager
            if app.state.complex_manager is None:
                app.state.complex_manager = SessionManager(app.state.sessions_root)
            complex_id = app.state.complex_manager.create(PuzzleInput(content=canonical["text"]))
            session = {
                "session_id": session_id, "kind": "general", "status": "READY",
                "complex_session_id": complex_id,
            }
        app.state.sessions[session_id] = session
        return deepcopy(session)

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        session = app.state.sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Unknown session")
        return deepcopy(session)

    @app.post("/api/sessions/{session_id}/run")
    def run_session(session_id: str):
        session = app.state.sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Unknown session")
        if session["kind"] != "general":
            return deepcopy(session["result"])
        if app.state.agent_provider is None:
            raise HTTPException(503, "DEEPSEEK_API_KEY is required to run the complex Agent")
        result = app.state.complex_manager.run(
            session["complex_session_id"], app.state.agent_provider
        )
        session["status"] = result.get("status", "UNKNOWN")
        session["result"] = result
        return deepcopy(result)

    return app


app = create_app()
