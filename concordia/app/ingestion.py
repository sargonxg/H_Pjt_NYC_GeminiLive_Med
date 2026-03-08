"""
CONCORDIA Text Ingestion Pipeline

Handles document upload, format detection, and structured extraction
via the ADK agent pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import concordia_agent.ontology as ontology
from concordia_agent.ontology import ConflictGraph

logger = logging.getLogger(__name__)


# ── Format Detection & Normalization ────────────────────────────────────────

def detect_format(text: str) -> str:
    """Detect the input format: 'structured_json', 'email_chain', or 'plain_text'."""
    stripped = text.strip()

    # Try JSON
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if any(k in data for k in ("their_story", "party_name", "what_they_want", "key_events")):
                return "structured_json"
        except json.JSONDecodeError:
            pass

    # Email chain detection
    email_markers = ["From:", "Subject:", "Date:"]
    marker_count = sum(1 for m in email_markers if m in text)
    if marker_count >= 2:
        return "email_chain"

    return "plain_text"


def normalize_input(text: str, party_name: str = "") -> str:
    """Normalize input into a structured prompt for the agent."""
    fmt = detect_format(text)

    if fmt == "structured_json":
        try:
            data = json.loads(text.strip())
            parts = []
            name = data.get("party_name", party_name)
            if name:
                parts.append(f"Party: {name}")
            if data.get("their_story"):
                parts.append(f"Their story: {data['their_story']}")
            if data.get("what_they_want"):
                parts.append(f"What they want: {data['what_they_want']}")
            if data.get("key_events"):
                events = data["key_events"]
                if isinstance(events, list):
                    parts.append("Key events:\n" + "\n".join(f"- {e}" for e in events))
            if data.get("documents"):
                docs = data["documents"]
                if isinstance(docs, list):
                    for i, doc in enumerate(docs, 1):
                        parts.append(f"\n--- Document {i} ---\n{doc}")
            return "\n\n".join(parts)
        except (json.JSONDecodeError, AttributeError):
            pass

    if fmt == "email_chain":
        # Structure the email chain with clear separators
        emails = re.split(r"(?=From:\s)", text)
        structured = []
        for i, email in enumerate(emails):
            email = email.strip()
            if email:
                structured.append(f"--- Email {i + 1} ---\n{email}")
        return f"Email chain from {party_name}:\n\n" + "\n\n".join(structured)

    # plain_text
    return text


# ── Ingestion Orchestrator ──────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are CONCORDIA's document analyst. A party in a mediation has submitted written material.

Your task: SILENTLY and THOROUGHLY extract ALL conflict primitives from this document.

For each piece of information you find, call the appropriate tool:
- People, organizations, groups mentioned → add_actor
- Demands, accusations, grievances, proposals → add_claim
- Underlying needs and motivations → add_interest
- Legal, financial, time, or structural limits → add_constraint
- Power dynamics, threats, incentives → add_leverage
- Promises, agreements, obligations → add_commitment
- Timeline events, triggers, escalations → add_event
- Framing, perspective, narrative themes → add_narrative
- If a document is included, call ingest_document first

After extraction, call set_case_info if you can determine the case title and summary.

Be EXHAUSTIVE — extract everything relevant. Call multiple tools. Do NOT respond conversationally.
After all extractions, provide a brief summary of what you found: how many actors, claims, interests, etc."""


async def ingest_text_for_party(
    runner: Runner,
    session_service: InMemorySessionService,
    app_name: str,
    graph: ConflictGraph,
    party_id: str,
    party_name: str,
    text: str,
    document_name: str = "Uploaded Document",
) -> dict:
    """Ingest text for a party by running it through the ADK agent pipeline.

    Sets the module-level graph and active_party so tools write to the correct graph,
    then creates a temporary session and sends the text through the agent.

    Returns dict with ingestion results and health check.
    """
    # Set the active context for tools
    ontology.graph = graph
    ontology.active_party = party_id

    # Normalize the input text
    normalized = normalize_input(text, party_name)

    # Create a temporary session for ingestion
    ingestion_session_id = f"ingest_{uuid.uuid4().hex[:8]}"
    session = await session_service.create_session(
        app_name=app_name,
        user_id=party_id,
        session_id=ingestion_session_id,
    )

    # Build the ingestion message
    message = f"""[DOCUMENT UPLOAD — Silent Extraction Mode]
Party: {party_name} (ID: {party_id})
Document: {document_name}

{EXTRACTION_SYSTEM_PROMPT}

--- BEGIN DOCUMENT ---
{normalized}
--- END DOCUMENT ---"""

    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    # Run the agent synchronously (non-live mode) for text extraction
    agent_response_parts = []
    try:
        async for event in runner.run(
            user_id=party_id,
            session_id=ingestion_session_id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        agent_response_parts.append(part.text)
    except Exception as e:
        logger.error(f"Ingestion agent error for party {party_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "health": graph.health_check(),
        }

    # Run health check after ingestion
    health = graph.health_check()
    party_health = graph.per_party_health_check(party_id)

    return {
        "status": "ingested",
        "document_name": document_name,
        "party_id": party_id,
        "party_name": party_name,
        "format_detected": detect_format(text),
        "agent_summary": " ".join(agent_response_parts)[:500] if agent_response_parts else "",
        "health": health,
        "party_health": party_health,
    }
