"""
CONCORDIA — FastAPI Bidi-Streaming Server

4-phase ADK lifecycle for real-time AI mediation:
  Phase 1: Application initialization (startup singletons)
  Phase 2: Session initialization (per WebSocket connection)
  Phase 3: Bidirectional streaming (upstream + downstream tasks)
  Phase 4: Graceful termination (close LiveRequestQueue)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path

# Load .env BEFORE importing agent so CONCORDIA_MODEL is available
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from concordia_agent import root_agent, graph
import concordia_agent.ontology as ontology

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Phase 1: Application Initialization ─────────────────────────────────────

APP_NAME = "concordia"

app = FastAPI(title="CONCORDIA — Live AI Mediation Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/graph")
async def get_graph():
    """Return the full conflict graph as JSON."""
    return json.loads(graph.model_dump_json())


@app.get("/api/health")
async def get_health():
    """Return the graph health check."""
    return graph.health_check()


@app.get("/api/status")
async def get_status():
    """Return a summary of the current mediation state."""
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


# ── Phase 2-4: WebSocket Endpoint ───────────────────────────────────────────

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connected: user={user_id}, session={session_id}")

    # Phase 2: Session Initialization
    ontology.active_party = user_id
    if user_id not in graph.parties:
        graph.parties.append(user_id)

    # Auto-detect model capabilities
    model_name = os.getenv("CONCORDIA_MODEL", "gemini-2.0-flash")
    if "native-audio" in model_name:
        run_config = RunConfig(
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
    else:
        run_config = RunConfig(
            response_modalities=["TEXT"],
            session_resumption=types.SessionResumptionConfig(),
            streaming_mode=StreamingMode.BIDI,
        )

    live_request_queue = LiveRequestQueue()

    # Get or create session
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        logger.info(f"Created new session: {session_id}")

    # Send initial graph state
    try:
        await websocket.send_json({
            "type": "graph_update",
            "graph": json.loads(graph.model_dump_json()),
            "health": graph.health_check(),
        })
    except Exception:
        pass

    # Phase 3: Bidirectional Streaming

    async def upstream_task():
        """Client → LiveRequestQueue: forward text, images, and audio."""
        try:
            while True:
                data = await websocket.receive()

                if "text" in data:
                    msg = json.loads(data["text"])

                    if msg.get("type") == "text":
                        ontology.active_party = user_id
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
                    # Raw PCM audio bytes (16kHz, 16-bit, mono)
                    live_request_queue.send_realtime(
                        types.Blob(
                            data=data["bytes"],
                            mime_type="audio/pcm;rate=16000",
                        )
                    )

        except WebSocketDisconnect:
            logger.info(f"Client disconnected (upstream): {user_id}")

    async def downstream_task():
        """run_live() events → Client: forward text, audio, tool calls, and graph updates."""
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
                        await websocket.send_json({
                            "type": "text",
                            "content": part.text,
                            "author": event.author or "concordia",
                        })

                    # Audio response
                    if hasattr(part, "inline_data") and part.inline_data:
                        if "audio" in (part.inline_data.mime_type or ""):
                            await websocket.send_bytes(part.inline_data.data)

                    # Tool call → send tool info AND updated graph
                    if hasattr(part, "function_call") and part.function_call:
                        await websocket.send_json({
                            "type": "tool_call",
                            "tool": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {},
                        })
                        await websocket.send_json({
                            "type": "graph_update",
                            "graph": json.loads(graph.model_dump_json()),
                            "health": graph.health_check(),
                        })

        except WebSocketDisconnect:
            logger.info(f"Client disconnected (downstream): {user_id}")

    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except Exception as e:
        logger.error(f"Session error for {user_id}: {e}")
    finally:
        # Phase 4: Graceful Termination
        live_request_queue.close()
        logger.info(f"Session closed: user={user_id}, session={session_id}")


# ── Static File Serving ─────────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"


@app.get("/")
async def serve_index():
    """Serve the frontend."""
    return FileResponse(static_dir / "index.html")


app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
