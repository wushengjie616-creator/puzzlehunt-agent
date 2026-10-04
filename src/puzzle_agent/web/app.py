from __future__ import annotations

import base64
from copy import deepcopy
import logging
import os
from pathlib import Path
import secrets
from threading import Lock, Thread
from typing import Any
from urllib.parse import urlparse
import uuid
from collections.abc import MutableMapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from puzzle_agent.config import load_env_local
from puzzle_agent.domain import PuzzleInput
from puzzle_agent.intake.contracts import ReceiptError, ReceiptSigner, canonical_hash
from puzzle_agent.intake.normalizer import DeepSeekNormalizer, NormalizationError
from puzzle_agent.intake.uploads import UploadError, validate_image_upload
from puzzle_agent.paper_puzzle.gateway import PaperPuzzleGateway
from puzzle_agent.paper_puzzle.components.minesweeper import MinesweeperError, MinesweeperStore
from puzzle_agent.providers.deepseek import DeepSeekConfig, DeepSeekProvider
from puzzle_agent.cipher_reference import BRAILLE_TABLE, SEMAPHORE_TABLE, search_references, transform


_STATIC = Path(__file__).with_name("static")
_LOGGER = logging.getLogger(__name__)
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver", "::1"}


class _UnavailableNormalizer:
    reason = "DEEPSEEK_API_KEY 未配置；请在项目根目录配置 .env 或 .env.local 后重启服务"

    def normalize(self, **kwargs):
        raise RuntimeError(self.reason)


def _default_normalizer(environ: MutableMapping[str, str] | None = None):
    target = os.environ if environ is None else environ
    load_env_local(environ=target)
    api_key = target.get("DEEPSEEK_API_KEY")
    if not api_key:
        return _UnavailableNormalizer()
    provider = DeepSeekProvider(DeepSeekConfig(
        api_key=api_key,
        base_url=target.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=target.get("DEEPSEEK_VISION_MODEL", "deepseek-flash"),
        thinking="disabled",
        reasoning_effort="low",
        max_tokens=8192,
    ))
    return DeepSeekNormalizer(provider)


def _default_agent_provider(environ: MutableMapping[str, str] | None = None):
    target = os.environ if environ is None else environ
    load_env_local(environ=target)
    api_key = target.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return DeepSeekProvider(DeepSeekConfig(
        api_key=api_key,
        base_url=target.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=target.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    ))


def create_app(
    *,
    normalizer=None,
    agent_provider=None,
    receipt_secret: bytes | None = None,
    capability_token: str | None = None,
    sessions_root: Path | None = None,
    env: MutableMapping[str, str] | None = None,
) -> FastAPI:
    app = FastAPI(title="Puzzle Agent Local Web", docs_url=None, redoc_url=None)
    target_env = os.environ if env is None else env
    app.state.normalizer = normalizer if normalizer is not None else _default_normalizer(target_env)
    app.state.agent_provider = agent_provider if agent_provider is not None else _default_agent_provider(target_env)
    if normalizer is not None:
        app.state.deepseek_status = {
            "configured": True,
            "status": "injected-test-provider",
            "message": "使用注入的规范化 provider。",
            "vision_model": "injected",
            "agent_model": "injected" if agent_provider is not None else None,
        }
    else:
        configured = bool(target_env.get("DEEPSEEK_API_KEY"))
        app.state.deepseek_status = {
            "configured": configured,
            "status": "configured" if configured else "missing-api-key",
            "message": (
                "DeepSeek 已配置；该状态不验证网络、余额或 Key 有效性。"
                if configured else _UnavailableNormalizer.reason
            ),
            "vision_model": target_env.get("DEEPSEEK_VISION_MODEL", "deepseek-flash"),
            "agent_model": target_env.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        }
    app.state.signer = ReceiptSigner(receipt_secret or secrets.token_bytes(32))
    app.state.capability = capability_token or secrets.token_urlsafe(32)
    app.state.gateway = PaperPuzzleGateway()
    app.state.minesweeper = MinesweeperStore(max_games=64)
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

    @app.get("/paper-puzzles")
    def paper_puzzles():
        return FileResponse(_STATIC / "paper-puzzles.html")

    @app.get("/cipher-tools")
    def cipher_tools():
        return FileResponse(_STATIC / "cipher-tools.html")

    @app.get("/static/{name}")
    def static_asset(name: str):
        if name not in {
            "app.js", "cipher-tools.js", "paper-puzzles.js",
            "styles.css", "sudoku-navigation.js", "agent-trace.js", "response-error.js",
        }:
            raise HTTPException(404)
        return FileResponse(_STATIC / name)

    @app.get("/static/assets/{name}")
    def static_image_asset(name: str):
        if name != "pigpen-reference-gpt.png":
            raise HTTPException(404)
        return FileResponse(_STATIC / "assets" / name)

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
            "deepseek": deepcopy(app.state.deepseek_status),
        }

    @app.get("/api/ciphers/references")
    def cipher_references(q: str = ""):
        try:
            return {
                "items": search_references(q),
                "braille_table": BRAILLE_TABLE,
                "semaphore_table": SEMAPHORE_TABLE,
            }
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/ciphers/transform")
    async def cipher_transform(request: Request):
        body = await request.json()
        try:
            return transform(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def get_minesweeper_game(game_id: str):
        try:
            return app.state.minesweeper.get(game_id)
        except MinesweeperError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/minesweeper/games", status_code=201)
    async def create_minesweeper_game(request: Request):
        body = await request.json()
        difficulty = body.get("difficulty") if isinstance(body, dict) else None
        try:
            game_id, game = app.state.minesweeper.create(difficulty)
        except MinesweeperError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"game_id": game_id, **game.public_state()}

    @app.get("/api/minesweeper/games/{game_id}")
    def get_minesweeper_state(game_id: str):
        return {"game_id": game_id, **get_minesweeper_game(game_id).public_state()}

    @app.post("/api/minesweeper/games/{game_id}/actions")
    async def act_on_minesweeper_game(game_id: str, request: Request):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "JSON object required")
        action = body.get("action")
        row, column = body.get("row"), body.get("column")
        game = get_minesweeper_game(game_id)
        try:
            if action == "reveal":
                state = game.reveal(row, column)
            elif action == "flag":
                state = game.toggle_flag(row, column)
            elif action == "chord":
                state = game.chord(row, column)
            else:
                raise MinesweeperError("action must be reveal, flag, or chord")
        except MinesweeperError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"game_id": game_id, **state}

    @app.post("/api/minesweeper/games/{game_id}/hint")
    def hint_minesweeper_game(game_id: str):
        return get_minesweeper_game(game_id).logical_hint()

    def add_event(record: dict[str, Any], event: str, detail: str) -> None:
        record["events"].append({"id": len(record["events"]) + 1, "event": event, "detail": detail})

    def run_normalization(
        intake_id: str,
        text: str,
        image: bytes | None,
        image_mime: str | None,
        preferred_kind: str | None,
    ) -> None:
        record = app.state.intakes[intake_id]
        try:
            record["status"] = "NORMALIZING"
            add_event(record, "normalizing", "DeepSeek NORMALIZE_INPUT started")
            result = app.state.normalizer.normalize(
                text=text,
                image=image,
                image_mime=image_mime,
                preferred_kind=preferred_kind,
            )
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
        preferred_kind = body.get("preferred_kind")
        if preferred_kind not in {None, "sudoku", "nonogram", "rule_puzzle", "general"}:
            raise HTTPException(
                400, "preferred_kind must be sudoku, nonogram, rule_puzzle, general, or null"
            )
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
        record = {
            "intake_id": intake_id,
            "status": "QUEUED",
            "preferred_kind": preferred_kind,
            "events": [],
        }
        add_event(record, "queued", "Input accepted by local safety gate")
        app.state.intakes[intake_id] = record
        Thread(
            target=run_normalization,
            args=(intake_id, text, image_data, image_mime, preferred_kind),
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
        body = await request.json()
        canonical = body.get("canonical") if isinstance(body, dict) else None
        if record["status"] == "CONFIRMED":
            if canonical == record.get("confirmed_canonical"):
                return {
                    "intake_id": intake_id,
                    "receipt": record["receipt"],
                    "canonical_hash": canonical_hash(canonical),
                }
            raise HTTPException(409, "Intake was already confirmed with different input")
        if record["status"] != "READY_FOR_CONFIRMATION":
            raise HTTPException(409, "Intake is not ready for confirmation")
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
        solve_mode = body.get("solve_mode", "full")
        if solve_mode not in {"full", "next_step"}:
            raise HTTPException(400, "solve_mode must be full or next_step")
        if kind not in {"sudoku", "rule_puzzle"} and solve_mode != "full":
            raise HTTPException(
                422, "solve_mode next_step is only supported for sudoku and rule_puzzle"
            )
        if kind in {"sudoku", "nonogram", "rule_puzzle"}:
            if kind == "rule_puzzle" and app.state.agent_provider is None:
                raise HTTPException(503, "rule_puzzle method synthesis provider is unavailable")
            try:
                result = app.state.gateway.run(
                    {"kind": kind, "canonical": canonical},
                    solve_mode=solve_mode,
                    provider=app.state.agent_provider if kind == "rule_puzzle" else None,
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            if (
                kind in {"sudoku", "nonogram"}
                and result["status"] == "STALLED"
                and app.state.agent_provider is not None
            ):
                try:
                    result["advisory"] = app.state.gateway.advise_stall(
                        result, app.state.agent_provider, kind=kind
                    )
                except (RuntimeError, ValueError) as exc:
                    result["advisory"] = {
                        "status": "UNVERIFIED_ADVISORY",
                        "message": f"Advisory unavailable: {exc}",
                    }
            session = {
                "session_id": session_id,
                "kind": kind,
                "solve_mode": solve_mode,
                "status": result["status"],
                "result": result,
            }
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
        session["status"] = "RUNNING"
        try:
            result = app.state.complex_manager.run(
                session["complex_session_id"], app.state.agent_provider
            )
        except Exception as exc:
            session["status"] = "FAILED"
            _LOGGER.exception("Complex Agent run failed for session %s", session_id)
            raise HTTPException(
                500, "Agent run failed; inspect the local server log for details"
            ) from exc
        session["status"] = result.get("status", "UNKNOWN")
        session["result"] = result
        return deepcopy(result)

    @app.post("/api/sessions/{session_id}/stop", status_code=202)
    def stop_session(session_id: str):
        session = app.state.sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Unknown session")
        if session["kind"] != "general" or app.state.complex_manager is None:
            raise HTTPException(409, "Only a running general Agent session can be stopped")
        try:
            result = app.state.complex_manager.request_stop(session["complex_session_id"])
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        session["status"] = "STOP_REQUESTED"
        return deepcopy(result)

    return app


app = create_app()
