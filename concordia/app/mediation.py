"""
CONCORDIA Multi-Party Mediation Manager

Manages mediation cases with multiple parties, phase progression,
and per-case conflict graphs.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from concordia_agent.ontology import ConflictGraph
from config import get_settings


# ── Enums ────────────────────────────────────────────────────────────────────

class PartyStatus(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETE = "complete"


class MediationPhase(StrEnum):
    INTAKE_PARTY_1 = "intake_party_1"
    INTAKE_PARTY_2 = "intake_party_2"
    JOINT_SESSION = "joint_session"
    RESOLUTION = "resolution"


# ── Models ───────────────────────────────────────────────────────────────────

class PartyState(BaseModel):
    party_id: str
    display_name: str
    status: PartyStatus = PartyStatus.WAITING
    session_id: str = ""
    connected: bool = False
    intake_complete: bool = False


class MediationCase(BaseModel):
    case_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    graph: ConflictGraph = Field(default_factory=ConflictGraph)
    parties: dict[str, PartyState] = Field(default_factory=dict)
    phase: MediationPhase = MediationPhase.INTAKE_PARTY_1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Track connected WebSocket references (not serialized)
    _ws_connections: dict[str, object] = {}
    _lock: asyncio.Lock | None = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            object.__setattr__(self, "_lock", asyncio.Lock())
        return self._lock

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def party_order(self) -> list[str]:
        """Return party_ids in insertion order."""
        return list(self.parties.keys())

    def active_party_id(self) -> str | None:
        """Return the party_id whose intake is currently active."""
        for pid, ps in self.parties.items():
            if ps.status == PartyStatus.ACTIVE:
                return pid
        return None

    def advance_phase(self) -> MediationPhase:
        """Advance to the next mediation phase. Returns the new phase."""
        order = list(MediationPhase)
        idx = order.index(self.phase)
        if idx < len(order) - 1:
            self.phase = order[idx + 1]
        self.touch()
        return self.phase

    def check_party_readiness(self, party_id: str) -> dict:
        """Check if a specific party's intake data is sufficient."""
        settings = get_settings()
        health = self.graph.per_party_health_check(party_id)
        ready = health["score"] >= settings.HEALTH_THRESHOLD_PARTY
        if ready:
            ps = self.parties.get(party_id)
            if ps:
                ps.intake_complete = True
        return {**health, "ready_for_next": ready}

    def summary(self) -> dict:
        """Return a JSON-serializable summary of the case."""
        return {
            "case_id": self.case_id,
            "title": self.title or self.graph.case_title,
            "phase": self.phase,
            "parties": {
                pid: ps.model_dump() for pid, ps in self.parties.items()
            },
            "graph_health": self.graph.health_check(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ── Case Manager Singleton ──────────────────────────────────────────────────

class CaseManager:
    """Manages all active mediation cases."""

    def __init__(self) -> None:
        self.active_cases: dict[str, MediationCase] = {}
        self._lock = asyncio.Lock()

    async def create_case(self, party_names: list[str], title: str = "") -> MediationCase:
        settings = get_settings()
        if len(party_names) < 2:
            raise ValueError("A mediation case requires at least 2 parties.")
        if len(party_names) > settings.MAX_PARTIES_PER_CASE:
            raise ValueError(f"Maximum {settings.MAX_PARTIES_PER_CASE} parties per case.")

        case = MediationCase(title=title)

        for i, name in enumerate(party_names):
            pid = f"party_{uuid.uuid4().hex[:6]}"
            status = PartyStatus.ACTIVE if i == 0 else PartyStatus.WAITING
            case.parties[pid] = PartyState(
                party_id=pid,
                display_name=name,
                status=status,
            )
            case.graph.parties.append(name)

        async with self._lock:
            self.active_cases[case.case_id] = case
        return case

    async def get_case(self, case_id: str) -> MediationCase | None:
        return self.active_cases.get(case_id)

    async def list_cases(self) -> list[dict]:
        return [c.summary() for c in self.active_cases.values()]


# Module-level singleton
case_manager = CaseManager()
