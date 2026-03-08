"""
CONCORDIA — FastAPI Bidi-Streaming Server

Multi-party mediation server with:
  - Per-case conflict graphs shared across parties
  - Sequential party intake with private sessions
  - Text document upload and ingestion pipeline
  - REST API for case management
  - WebSocket bidi-streaming for real-time mediation
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel as PydanticBaseModel, Field

from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from concordia_agent import root_agent, graph
import concordia_agent.ontology as ontology
from config import get_settings
from mediation import case_manager, MediationCase, MediationPhase, PartyStatus
from ingestion import ingest_text_for_party

# ── Logging Setup ────────────────────────────────────────────────────────────

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("concordia")


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

session_service = InMemorySessionService()
runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)

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


# ── REST Endpoints — Legacy (global graph) ──────────────────────────────────

@app.get("/api/graph")
async def get_graph():
    """Return the full conflict graph as JSON (legacy global graph)."""
    return json.loads(graph.model_dump_json())


@app.get("/api/health")
async def get_health():
    """Health check — includes Gemini API connectivity test."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_status = "configured" if api_key else "no_api_key"
    return {
        "status": "healthy",
        "gemini_api": gemini_status,
        "graph_health": graph.health_check(),
        "active_cases": len(case_manager.active_cases),
    }


@app.get("/api/status")
async def get_status():
    """Return a summary of the current mediation state (legacy global graph)."""
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
    }


@app.post("/api/set-key")
async def set_api_key(req: ApiKeyRequest):
    """Set the Gemini API key at runtime (hackathon demo only)."""
    os.environ["GOOGLE_API_KEY"] = req.key
    logger.info("API key updated at runtime.")
    return {"status": "ok"}


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

    # Point the global graph to this case's graph for tool access
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

    # Broadcast updated graph to connected clients
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

    # When advancing from intake, mark current active party as complete
    # and activate the next waiting party
    if case.phase in (MediationPhase.INTAKE_PARTY_1, MediationPhase.INTAKE_PARTY_2):
        for pid, ps in case.parties.items():
            if ps.status == PartyStatus.ACTIVE:
                ps.status = PartyStatus.COMPLETE
                ps.intake_complete = True
                break

        # Activate next waiting party
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
    await websocket.accept()
    logger.info(f"WebSocket connected (legacy): user={user_id}, session={session_id}")

    # Phase 2: Session Initialization
    ontology.active_party = user_id
    if user_id not in graph.parties:
        graph.parties.append(user_id)

    run_config = _build_run_config()
    live_request_queue = LiveRequestQueue()

    # Get or create session
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    # Send initial graph state
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

    # Register connection
    party.connected = True
    party.session_id = session_id
    ws_connections.setdefault(case_id, {})[party_id] = websocket

    # Point global graph to this case's graph
    ontology.graph = case.graph
    ontology.active_party = party_id

    run_config = _build_run_config()
    live_request_queue = LiveRequestQueue()

    # Get or create session
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=party_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=party_id, session_id=session_id
        )
        logger.info(f"Created session | {ctx}")

    # Send initial graph state
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
        # Cleanup on disconnect
        party.connected = False
        case_ws = ws_connections.get(case_id, {})
        case_ws.pop(party_id, None)
        if not case_ws:
            ws_connections.pop(case_id, None)
        logger.info(f"WebSocket disconnected | {ctx}")


# ── Shared Session Logic ────────────────────────────────────────────────────

def _build_run_config() -> RunConfig:
    """Build RunConfig based on model capabilities."""
    model_name = os.getenv("CONCORDIA_MODEL", "gemini-2.0-flash")
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
    live_request_queue: LiveRequestQueue,
    run_config: RunConfig,
    target_graph,
    case: MediationCase | None = None,
    party_id: str = "",
):
    """Run bidirectional streaming session (shared between legacy and multi-party)."""

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
                        # Set active context before each message
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
                    # Text response
                    if hasattr(part, "text") and part.text:
                        try:
                            await websocket.send_json({
                                "type": "text",
                                "content": part.text,
                                "author": event.author or "concordia",
                            })
                        except Exception:
                            return

                    # Audio response
                    if hasattr(part, "inline_data") and part.inline_data:
                        if "audio" in (part.inline_data.mime_type or ""):
                            try:
                                await websocket.send_bytes(part.inline_data.data)
                            except Exception:
                                return

                    # Tool call -> send tool info AND updated graph
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

                            # Broadcast to other parties in the same case
                            if case:
                                await broadcast_graph_update(case, exclude_ws=websocket)

                                # Check party readiness after tool calls
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
            else:
                logger.error(f"Downstream error for {user_id}: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "content": "An unexpected error occurred. Your data is saved — please reconnect.",
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
    """Serve the frontend."""
    return FileResponse(static_dir / "index.html")


@app.get("/workbench")
async def serve_workbench():
    """Serve the developer workbench."""
    wb = static_dir / "workbench.html"
    if wb.exists():
        return FileResponse(wb)
    return FileResponse(static_dir / "index.html")


app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
