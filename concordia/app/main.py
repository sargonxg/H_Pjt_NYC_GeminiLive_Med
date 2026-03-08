"""
CONCORDIA — FastAPI Bidi-Streaming Server

Multi-party mediation server with:
  - Per-case conflict graphs shared across parties
  - Sequential party intake with private sessions
  - Text document upload and ingestion pipeline
  - REST API for case management
  - WebSocket bidi-streaming for real-time mediation
  - Graceful fallback if Google ADK / API key is unavailable
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Load .env BEFORE importing agent so CONCORDIA_MODEL is available
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel as PydanticBaseModel, Field

from config import get_settings
from mediation import case_manager, MediationCase, MediationPhase, PartyStatus

# ── Logging Setup ────────────────────────────────────────────────────────────

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("concordia")

# ── ADK / Agent Initialization (with graceful fallback) ──────────────────────

_adk_errors: list[str] = []          # startup errors, shown on /api/diagnostics
_adk_available: bool = False          # True only if all imports + runner init succeeded

root_agent = None
graph = None
session_service = None
runner = None
ingest_text_for_party = None

def _try_import_adk() -> bool:
    """Attempt to import and initialize the Google ADK stack.

    Returns True on success, False if any step fails.
    All errors are recorded in _adk_errors for display on the status page.
    """
    global root_agent, graph, session_service, runner, ingest_text_for_party, _adk_available

    # 1. Google GenAI
    try:
        from google.genai import types as _genai_types  # noqa: F401
    except Exception as e:
        _adk_errors.append(f"google-genai import failed: {e}")
        return False

    # 2. Google ADK
    try:
        from google.adk.agents.live_request_queue import LiveRequestQueue  # noqa: F401
        from google.adk.agents.run_config import RunConfig, StreamingMode   # noqa: F401
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
    except Exception as e:
        _adk_errors.append(f"google-adk import failed: {e}")
        return False

    # 3. Our agent code
    try:
        from concordia_agent.agent import root_agent as _ra
        from concordia_agent.ontology import graph as _graph
        import concordia_agent.ontology as _ontology  # noqa: F401
    except Exception as e:
        _adk_errors.append(f"concordia_agent import failed: {e}")
        return False

    # 4. Ingestion pipeline
    try:
        from ingestion import ingest_text_for_party as _ingest
    except Exception as e:
        _adk_errors.append(f"ingestion module import failed: {e}")
        return False

    # 5. Runner init
    try:
        _session_service = InMemorySessionService()
        _runner = Runner(
            app_name=APP_NAME,
            agent=_ra,
            session_service=_session_service,
        )
    except Exception as e:
        _adk_errors.append(f"ADK Runner init failed: {e}")
        return False

    # All good — set module-level references
    root_agent = _ra
    graph = _graph
    session_service = _session_service
    runner = _runner
    ingest_text_for_party = _ingest
    _adk_available = True
    logger.info("ADK stack initialized successfully.")
    return True


def _try_import_ontology():
    """Import ontology separately for graph ops even if ADK fails."""
    try:
        from concordia_agent.ontology import ConflictGraph, graph as _graph
        return _graph
    except Exception:
        return None


def log_ctx(case_id: str = "", party_id: str = "") -> str:
    """Build a correlation context string for structured logging."""
    parts = []
    if case_id:
        parts.append(f"case={case_id}")
    if party_id:
        parts.append(f"party={party_id}")
    return " ".join(parts)


# ── Phase 1: Application Initialization ─────────────────────────────────────

APP_NAME = "concordia"

app = FastAPI(title="CONCORDIA — Live AI Mediation Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to bring up the ADK stack at startup; failure is non-fatal
_try_import_adk()

# Fallback graph for status reporting when ADK is unavailable
if graph is None:
    graph = _try_import_ontology()

# Track WebSocket connections per case for broadcasting
# { case_id: { party_id: WebSocket } }
ws_connections: dict[str, dict[str, WebSocket]] = {}


# ── Request/Response Models ──────────────────────────────────────────────────

class ApiKeyRequest(PydanticBaseModel):
    key: str


class CreateCaseRequest(PydanticBaseModel):
    title: str = ""
    parties: list[str] = Field(..., min_length=2)


class UploadDocumentRequest(PydanticBaseModel):
    party_id: str
    text: str
    document_name: str = "Uploaded Document"


class AdvanceCaseRequest(PydanticBaseModel):
    pass


# ── Helper: broadcast graph to all connected parties ────────────────────────

async def broadcast_graph_update(case: MediationCase, exclude_ws: WebSocket | None = None):
    """Send graph_update to ALL connected WebSockets for this case."""
    case_ws = ws_connections.get(case.case_id, {})
    graph_data = json.loads(case.graph.model_dump_json())
    health = case.graph.health_check()
    message = {
        "type": "graph_update",
        "graph": graph_data,
        "health": health,
    }
    for pid, ws in list(case_ws.items()):
        if ws is exclude_ws:
            continue
        try:
            await ws.send_json(message)
        except Exception:
            pass


# ── REST Endpoints — Diagnostics & Health ───────────────────────────────────

@app.get("/api/health")
async def get_health():
    """Health check — includes Gemini API connectivity test."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_status = "configured" if api_key else "no_api_key"

    graph_health = None
    if graph is not None:
        try:
            graph_health = graph.health_check()
        except Exception as e:
            graph_health = {"error": str(e)}

    return {
        "status": "healthy",
        "adk_available": _adk_available,
        "gemini_api": gemini_status,
        "graph_health": graph_health,
        "active_cases": len(case_manager.active_cases),
        "startup_errors": _adk_errors,
        "python_version": sys.version,
        "model": os.getenv("CONCORDIA_MODEL", "gemini-3-flash-preview"),
    }


@app.get("/api/diagnostics")
async def get_diagnostics():
    """Full system diagnostics — checks all components."""
    diagnostics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "environment": {
            "PORT": os.getenv("PORT", "8080"),
            "CONCORDIA_MODEL": os.getenv("CONCORDIA_MODEL", "gemini-3-flash-preview"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "GOOGLE_API_KEY": "SET" if os.getenv("GOOGLE_API_KEY") else "MISSING",
            "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "*"),
        },
        "components": {},
        "startup_errors": _adk_errors,
        "adk_available": _adk_available,
        "active_cases": len(case_manager.active_cases),
    }

    # Check individual packages
    packages = [
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
        ("uvicorn", "uvicorn"),
        ("google.genai", "google-genai"),
        ("google.adk", "google-adk"),
        ("dotenv", "python-dotenv"),
    ]
    for module, label in packages:
        try:
            __import__(module)
            version = "ok"
            try:
                import importlib.metadata
                version = importlib.metadata.version(label)
            except Exception:
                pass
            diagnostics["components"][label] = {"status": "ok", "version": version}
        except ImportError as e:
            diagnostics["components"][label] = {"status": "missing", "error": str(e)}

    # Check ADK submodules
    adk_modules = [
        "google.adk.agents",
        "google.adk.runners",
        "google.adk.sessions",
    ]
    for mod in adk_modules:
        try:
            __import__(mod)
            diagnostics["components"][mod] = {"status": "ok"}
        except Exception as e:
            diagnostics["components"][mod] = {"status": "error", "error": str(e)}

    # Check static files
    static_dir = Path(__file__).parent / "static"
    diagnostics["static_files"] = {
        "directory_exists": static_dir.exists(),
        "index_html": (static_dir / "index.html").exists(),
    }

    # Graph health
    if graph is not None:
        try:
            diagnostics["graph_health"] = graph.health_check()
        except Exception as e:
            diagnostics["graph_health"] = {"error": str(e)}
    else:
        diagnostics["graph_health"] = None

    return diagnostics


# ── REST Endpoints — Legacy (global graph) ──────────────────────────────────

@app.get("/api/graph")
async def get_graph():
    """Return the full conflict graph as JSON (legacy global graph)."""
    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not available — ADK init failed")
    return json.loads(graph.model_dump_json())


@app.get("/api/status")
async def get_status():
    """Return a summary of the current mediation state (legacy global graph)."""
    if graph is None:
        return {
            "title": "",
            "phase": "unavailable",
            "parties": [],
            "counts": {},
            "health": None,
            "adk_available": False,
            "errors": _adk_errors,
        }
    return {
        "title": graph.case_title,
        "phase": graph.phase,
        "parties": graph.parties,
        "counts": {
            "actors": len(graph.actors),
            "claims": len(graph.claims),
            "interests": len(graph.interests),
            "constraints": len(graph.constraints),
            "leverages": len(graph.leverages),
            "commitments": len(graph.commitments),
            "events": len(graph.events),
            "narratives": len(graph.narratives),
            "edges": len(graph.edges),
            "documents": len(graph.documents),
        },
        "health": graph.health_check(),
        "adk_available": _adk_available,
    }


@app.post("/api/set-key")
async def set_api_key(req: ApiKeyRequest):
    """Set the Gemini API key at runtime and attempt to re-initialize ADK."""
    if not req.key or not req.key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    os.environ["GOOGLE_API_KEY"] = req.key.strip()
    logger.info("API key updated at runtime — attempting ADK re-initialization.")

    # Re-try ADK initialization with the new key
    if not _adk_available:
        _adk_errors.clear()
        success = _try_import_adk()
        return {
            "status": "ok",
            "adk_reinitialized": success,
            "adk_available": _adk_available,
            "errors": _adk_errors if not success else [],
        }

    return {
        "status": "ok",
        "adk_reinitialized": False,
        "adk_available": _adk_available,
        "message": "ADK was already running; key updated for next requests.",
    }


# ── REST Endpoints — Case Management ────────────────────────────────────────

@app.post("/api/cases")
async def create_case(req: CreateCaseRequest):
    """Create a new mediation case with party names."""
    try:
        case = await case_manager.create_case(
            party_names=req.parties,
            title=req.title,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"Case created | {log_ctx(case.case_id)} parties={req.parties}")

    return {
        "case_id": case.case_id,
        "parties": [
            {
                "party_id": pid,
                "name": ps.display_name,
                "status": ps.status,
                "join_url": f"/ws/{case.case_id}/{pid}/{{session_id}}",
            }
            for pid, ps in case.parties.items()
        ],
    }


@app.get("/api/cases")
async def list_cases():
    """List all active mediation cases."""
    return await case_manager.list_cases()


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get full case status including graph, health, and party states."""
    case = await case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    graph_data = json.loads(case.graph.model_dump_json())
    return {
        **case.summary(),
        "graph": graph_data,
        "party_health": {
            pid: case.graph.per_party_health_check(pid)
            for pid in case.parties
        },
    }


@app.post("/api/cases/{case_id}/upload")
async def upload_document(case_id: str, req: UploadDocumentRequest):
    """Upload a text document for a specific party."""
    if not _adk_available or ingest_text_for_party is None:
        raise HTTPException(
            status_code=503,
            detail=f"AI agent unavailable — Google ADK not initialized. Errors: {_adk_errors}",
        )

    case = await case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    party = case.parties.get(req.party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found in this case")

    logger.info(
        f"Document upload | {log_ctx(case_id, req.party_id)} "
        f"doc={req.document_name} len={len(req.text)}"
    )

    # Import ontology at runtime (lazy)
    import concordia_agent.ontology as ontology
    ontology.graph = case.graph
    ontology.active_party = req.party_id

    try:
        result = await ingest_text_for_party(
            runner=runner,
            session_service=session_service,
            app_name=APP_NAME,
            graph=case.graph,
            party_id=req.party_id,
            party_name=party.display_name,
            text=req.text,
            document_name=req.document_name,
        )
    except Exception as e:
        logger.error(f"Ingestion error | {log_ctx(case_id, req.party_id)}: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    await broadcast_graph_update(case)
    case.touch()
    return result


@app.post("/api/cases/{case_id}/advance")
async def advance_case(case_id: str):
    """Manually advance the mediation phase."""
    case = await case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    old_phase = case.phase

    if case.phase in (MediationPhase.INTAKE_PARTY_1, MediationPhase.INTAKE_PARTY_2):
        for pid, ps in case.parties.items():
            if ps.status == PartyStatus.ACTIVE:
                ps.status = PartyStatus.COMPLETE
                ps.intake_complete = True
                break
        for pid, ps in case.parties.items():
            if ps.status == PartyStatus.WAITING:
                ps.status = PartyStatus.ACTIVE
                break

    new_phase = case.advance_phase()
    logger.info(f"Phase advanced | {log_ctx(case_id)} {old_phase} -> {new_phase}")

    return {
        "case_id": case_id,
        "previous_phase": old_phase,
        "current_phase": new_phase,
        "parties": {pid: ps.model_dump() for pid, ps in case.parties.items()},
    }


# ── WebSocket Endpoint — Legacy (global graph) ─────────────────────────────

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint_legacy(websocket: WebSocket, user_id: str, session_id: str):
    """Legacy single-user WebSocket endpoint (backwards compatible)."""
    if not _adk_available:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "content": f"AI agent unavailable. Errors: {'; '.join(_adk_errors)}",
            "error_type": "adk_unavailable",
            "adk_available": False,
        })
        await websocket.close(code=1011, reason="ADK not available")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected (legacy): user={user_id}, session={session_id}")

    import concordia_agent.ontology as ontology
    ontology.active_party = user_id
    if user_id not in graph.parties:
        graph.parties.append(user_id)

    run_config = _build_run_config()

    from google.adk.agents.live_request_queue import LiveRequestQueue
    live_request_queue = LiveRequestQueue()

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    try:
        await websocket.send_json({
            "type": "graph_update",
            "graph": json.loads(graph.model_dump_json()),
            "health": graph.health_check(),
        })
    except Exception:
        pass

    await _run_bidi_session(
        websocket=websocket,
        user_id=user_id,
        session_id=session_id,
        live_request_queue=live_request_queue,
        run_config=run_config,
        target_graph=graph,
    )


# ── WebSocket Endpoint — Multi-Party ───────────────────────────────────────

@app.websocket("/ws/{case_id}/{party_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, case_id: str, party_id: str, session_id: str):
    """Multi-party mediation WebSocket endpoint."""
    if not _adk_available:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "content": f"AI agent unavailable. Start by setting your Google API key at /api/set-key. Errors: {'; '.join(_adk_errors)}",
            "error_type": "adk_unavailable",
            "adk_available": False,
        })
        await websocket.close(code=1011, reason="ADK not available")
        return

    case = await case_manager.get_case(case_id)
    if not case:
        await websocket.close(code=4004, reason="Case not found")
        return

    party = case.parties.get(party_id)
    if not party:
        await websocket.close(code=4004, reason="Party not found")
        return

    await websocket.accept()
    ctx = log_ctx(case_id, party_id)
    logger.info(f"WebSocket connected | {ctx} session={session_id}")

    party.connected = True
    party.session_id = session_id
    ws_connections.setdefault(case_id, {})[party_id] = websocket

    import concordia_agent.ontology as ontology
    ontology.graph = case.graph
    ontology.active_party = party_id

    run_config = _build_run_config()

    from google.adk.agents.live_request_queue import LiveRequestQueue
    live_request_queue = LiveRequestQueue()

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=party_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=party_id, session_id=session_id
        )
        logger.info(f"Created session | {ctx}")

    try:
        await websocket.send_json({
            "type": "graph_update",
            "graph": json.loads(case.graph.model_dump_json()),
            "health": case.graph.health_check(),
        })
    except Exception:
        pass

    try:
        await _run_bidi_session(
            websocket=websocket,
            user_id=party_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
            target_graph=case.graph,
            case=case,
            party_id=party_id,
        )
    finally:
        party.connected = False
        case_ws = ws_connections.get(case_id, {})
        case_ws.pop(party_id, None)
        if not case_ws:
            ws_connections.pop(case_id, None)
        logger.info(f"WebSocket disconnected | {ctx}")


# ── Shared Session Logic ────────────────────────────────────────────────────

def _build_run_config():
    """Build RunConfig based on model capabilities."""
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types

    model_name = os.getenv("CONCORDIA_MODEL", "gemini-3-flash-preview")
    if "native-audio" in model_name:
        return RunConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            session_resumption=types.SessionResumptionConfig(),
            streaming_mode=StreamingMode.BIDI,
        )
    return RunConfig(
        response_modalities=["TEXT"],
        session_resumption=types.SessionResumptionConfig(),
        streaming_mode=StreamingMode.BIDI,
    )


async def _run_bidi_session(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
    live_request_queue,
    run_config,
    target_graph,
    case: MediationCase | None = None,
    party_id: str = "",
):
    """Run bidirectional streaming session (shared between legacy and multi-party)."""
    from google.genai import types

    async def upstream_task():
        """Client -> LiveRequestQueue: forward text, images, and audio."""
        try:
            while True:
                data = await websocket.receive()

                if "text" in data:
                    try:
                        msg = json.loads(data["text"])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from {user_id}")
                        continue

                    if msg.get("type") == "text":
                        import concordia_agent.ontology as ontology
                        ontology.active_party = party_id or user_id
                        ontology.graph = target_graph
                        content = types.Content(
                            role="user",
                            parts=[types.Part(text=msg["content"])],
                        )
                        live_request_queue.send_content(content)

                    elif msg.get("type") == "image":
                        image_bytes = base64.b64decode(msg["data"])
                        live_request_queue.send_realtime(
                            types.Blob(
                                data=image_bytes,
                                mime_type=msg.get("mime", "image/jpeg"),
                            )
                        )

                elif "bytes" in data:
                    live_request_queue.send_realtime(
                        types.Blob(
                            data=data["bytes"],
                            mime_type="audio/pcm;rate=16000",
                        )
                    )

        except WebSocketDisconnect:
            logger.info(f"Client disconnected (upstream): {user_id}")
        except Exception as e:
            logger.error(f"Upstream error for {user_id}: {e}")

    async def downstream_task():
        """run_live() events -> Client: forward text, audio, tool calls, graph updates."""
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                if not event.content or not event.content.parts:
                    continue

                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        try:
                            await websocket.send_json({
                                "type": "text",
                                "content": part.text,
                                "author": event.author or "concordia",
                            })
                        except Exception:
                            return

                    if hasattr(part, "inline_data") and part.inline_data:
                        if "audio" in (part.inline_data.mime_type or ""):
                            try:
                                await websocket.send_bytes(part.inline_data.data)
                            except Exception:
                                return

                    if hasattr(part, "function_call") and part.function_call:
                        try:
                            await websocket.send_json({
                                "type": "tool_call",
                                "tool": part.function_call.name,
                                "args": dict(part.function_call.args) if part.function_call.args else {},
                            })
                            graph_data = json.loads(target_graph.model_dump_json())
                            health = target_graph.health_check()
                            await websocket.send_json({
                                "type": "graph_update",
                                "graph": graph_data,
                                "health": health,
                            })

                            if case:
                                await broadcast_graph_update(case, exclude_ws=websocket)

                                if party_id:
                                    readiness = case.check_party_readiness(party_id)
                                    if readiness.get("ready_for_next"):
                                        await websocket.send_json({
                                            "type": "system",
                                            "content": f"Your intake data looks comprehensive (score: {readiness['score']}%). The mediator has a good picture of your perspective.",
                                        })

                        except Exception as e:
                            logger.error(f"Error sending tool update: {e}")
                            return

        except WebSocketDisconnect:
            logger.info(f"Client disconnected (downstream): {user_id}")
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "429" in error_msg or "resource_exhausted" in error_msg:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "content": "The AI service is temporarily at capacity. Please wait a moment and try again.",
                        "error_type": "quota_exhausted",
                    })
                except Exception:
                    pass
            elif "not found for api version" in error_msg or "not supported for bidigeneratecontent" in error_msg or "listmodels" in error_msg:
                model_name = os.getenv("CONCORDIA_MODEL", "gemini-3-flash-preview")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Model '{model_name}' does not support live streaming (bidiGenerateContent). Check that the model name is correct and supports this API.",
                        "error_type": "model_error",
                    })
                except Exception:
                    pass
            elif "api_key" in error_msg or "invalid_argument" in error_msg or "unauthenticated" in error_msg:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Invalid or missing Google API key. Please set your key via the Settings panel.",
                        "error_type": "auth_error",
                    })
                except Exception:
                    pass
            else:
                logger.error(f"Downstream error for {user_id}: {e}\n{traceback.format_exc()}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"An unexpected error occurred: {str(e)[:200]}. Your data is saved — please reconnect.",
                        "error_type": "internal",
                    })
                except Exception:
                    pass

    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except Exception as e:
        logger.error(f"Session error for {user_id}: {e}")
    finally:
        live_request_queue.close()
        logger.info(f"Session closed: user={user_id}, session={session_id}")


# ── Static File Serving ─────────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"


@app.get("/")
async def serve_index():
    """Serve the frontend — always works, shows status page if ADK unavailable."""
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    # Ultimate fallback: inline minimal HTML
    return HTMLResponse(content=_minimal_fallback_html(), status_code=200)


@app.get("/workbench")
async def serve_workbench():
    """Serve the developer workbench."""
    wb = static_dir / "workbench.html"
    if wb.exists():
        return FileResponse(str(wb))
    return FileResponse(str(static_dir / "index.html"))


@app.get("/status")
async def serve_status_page():
    """Dedicated system status page — always works."""
    status = static_dir / "status.html"
    if status.exists():
        return FileResponse(str(status))
    return HTMLResponse(content=_minimal_fallback_html(), status_code=200)


if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    logger.warning(f"Static directory not found: {static_dir}")


def _minimal_fallback_html() -> str:
    """Absolute minimal fallback HTML — shown when static files are missing."""
    api_key_set = bool(os.getenv("GOOGLE_API_KEY"))
    errors_html = "".join(f"<li>{e}</li>" for e in _adk_errors) if _adk_errors else "<li>No errors</li>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CONCORDIA — System Status</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #0a0a0f; color: #e0e0e0;
         max-width: 800px; margin: 40px auto; padding: 20px; }}
  h1 {{ color: #2abfac; }}
  .status {{ padding: 12px; border-radius: 8px; margin: 12px 0; }}
  .ok {{ background: #1a3a2a; border-left: 4px solid #6bbf8a; }}
  .warn {{ background: #3a2a1a; border-left: 4px solid #e8864d; }}
  .err {{ background: #3a1a1a; border-left: 4px solid #e85d5d; }}
  input {{ background: #1a1a2e; color: #e0e0e0; border: 1px solid #2abfac;
           padding: 10px; width: 100%; border-radius: 6px; margin: 8px 0; box-sizing: border-box; }}
  button {{ background: #2abfac; color: #0a0a0f; border: none; padding: 10px 20px;
            border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 8px; }}
  pre {{ background: #10101a; padding: 12px; border-radius: 6px; overflow-x: auto;
         font-size: 12px; }}
  a {{ color: #2abfac; }}
</style>
</head>
<body>
<h1>CONCORDIA</h1>
<p>AI-powered conflict mediation — system status page.</p>

<div class="status {'ok' if _adk_available else 'err'}">
  <strong>AI Engine:</strong> {'Running' if _adk_available else 'Not available'}
</div>

<div class="status {'ok' if api_key_set else 'warn'}">
  <strong>Google API Key:</strong> {'Configured' if api_key_set else 'Not set — required for AI features'}
</div>

{"<div class='status err'><strong>Startup Errors:</strong><ul>" + errors_html + "</ul></div>" if _adk_errors else ""}

<h2>Set API Key</h2>
<input type="password" id="apiKey" placeholder="AIza..." />
<button onclick="setKey()">Apply Key</button>
<div id="keyResult"></div>

<h2>Links</h2>
<ul>
  <li><a href="/api/diagnostics">Full Diagnostics (JSON)</a></li>
  <li><a href="/api/health">Health Check (JSON)</a></li>
  <li><a href="/api/cases">Active Cases (JSON)</a></li>
  <li><a href="/">Main Application</a></li>
</ul>

<script>
async function setKey() {{
  const key = document.getElementById('apiKey').value.trim();
  if (!key) return;
  const r = await fetch('/api/set-key', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ key }})
  }});
  const data = await r.json();
  document.getElementById('keyResult').innerHTML =
    '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
  if (data.adk_available) setTimeout(() => location.reload(), 1500);
}}
</script>
</body>
</html>"""


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
