"""
CONCORDIA Conflict Ontology

8 structural primitives that decompose any human dispute,
derived from UN Security Council mediation practice.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


# ── Type Enums ───────────────────────────────────────────────────────────────

class ActorType(StrEnum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    STATE = "state"
    GROUP = "group"
    INSTITUTION = "institution"


class ClaimType(StrEnum):
    DEMAND = "demand"
    ACCUSATION = "accusation"
    JUSTIFICATION = "justification"
    PROPOSAL = "proposal"
    GRIEVANCE = "grievance"


class InterestType(StrEnum):
    SECURITY = "security"
    ECONOMIC = "economic"
    IDENTITY = "identity"
    AUTONOMY = "autonomy"
    RECOGNITION = "recognition"
    PROCEDURAL = "procedural"


class ConstraintType(StrEnum):
    LEGAL = "legal"
    FINANCIAL = "financial"
    TEMPORAL = "temporal"
    NORMATIVE = "normative"
    STRUCTURAL = "structural"
    RELATIONAL = "relational"


class LeverageType(StrEnum):
    COERCIVE = "coercive"
    REWARD = "reward"
    INFORMATIONAL = "informational"
    NORMATIVE = "normative"
    RELATIONAL = "relational"
    STRUCTURAL = "structural"


class CommitmentStatus(StrEnum):
    ACTIVE = "active"
    BROKEN = "broken"
    FULFILLED = "fulfilled"


class EventType(StrEnum):
    TRIGGER = "trigger"
    ESCALATION = "escalation"
    DE_ESCALATION = "de_escalation"
    NEGOTIATION = "negotiation"
    AGREEMENT = "agreement"
    VIOLATION = "violation"


class Phase(StrEnum):
    ARRIVE = "arrive"
    STRUCTURE = "structure"
    VERIFY = "verify"
    RESOLVE = "resolve"


class EscalationLevel(StrEnum):
    LATENT = "latent"
    EMERGING = "emerging"
    ESCALATING = "escalating"
    CRISIS = "crisis"
    DESTRUCTIVE = "destructive"


# ── Helper ───────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


# ── Node Models ──────────────────────────────────────────────────────────────

class Actor(BaseModel):
    id: str = ""
    name: str
    actor_type: ActorType
    description: str = ""
    role_in_conflict: str = ""
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("actor")


class Claim(BaseModel):
    id: str = ""
    claim_type: ClaimType
    content: str
    source_actor_id: str
    target_actor_id: str = ""
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("claim")


class Interest(BaseModel):
    id: str = ""
    interest_type: InterestType
    description: str
    actor_id: str
    priority: int = Field(default=3, ge=1, le=5)
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("interest")


class Constraint(BaseModel):
    id: str = ""
    constraint_type: ConstraintType
    description: str
    affects_actor_ids: list[str] = Field(default_factory=list)
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("constraint")


class Leverage(BaseModel):
    id: str = ""
    leverage_type: LeverageType
    description: str
    held_by_actor_id: str
    target_actor_id: str = ""
    strength: int = Field(default=3, ge=1, le=5)
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("leverage")


class Commitment(BaseModel):
    id: str = ""
    description: str
    committed_actor_id: str
    to_actor_id: str = ""
    status: CommitmentStatus = CommitmentStatus.ACTIVE
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("commitment")


class Event(BaseModel):
    id: str = ""
    event_type: EventType
    description: str
    date: str = ""
    involved_actor_ids: list[str] = Field(default_factory=list)
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("event")


class Narrative(BaseModel):
    id: str = ""
    description: str
    held_by_actor_id: str
    frames: list[str] = Field(default_factory=list)
    contributed_by: str = "default"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = _uid("narrative")


# ── Edge Model ───────────────────────────────────────────────────────────────

class Edge(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    description: str = ""


# ── Document Record ──────────────────────────────────────────────────────────

class Document(BaseModel):
    name: str
    length: int
    contributed_by: str = "default"


# ── Conflict Graph ───────────────────────────────────────────────────────────

class ConflictGraph(BaseModel):
    case_title: str = ""
    case_summary: str = ""
    escalation_level: EscalationLevel = EscalationLevel.LATENT
    phase: Phase = Phase.ARRIVE

    actors: list[Actor] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    interests: list[Interest] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    leverages: list[Leverage] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    narratives: list[Narrative] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)

    def health_check(self) -> dict:
        """Evaluate graph completeness and return score, checks, gaps, ready."""
        actor_ids = {a.id for a in self.actors}
        actors_with_claims = {c.source_actor_id for c in self.claims} & actor_ids
        actors_with_interests = {i.actor_id for i in self.interests} & actor_ids
        actors_with_narratives = {n.held_by_actor_id for n in self.narratives} & actor_ids

        checks = {
            "two_plus_actors": len(self.actors) >= 2,
            "all_actors_have_claims": actor_ids == actors_with_claims if actor_ids else False,
            "all_actors_have_interests": actor_ids == actors_with_interests if actor_ids else False,
            "has_constraints": len(self.constraints) > 0,
            "has_leverage": len(self.leverages) > 0,
            "has_events": len(self.events) > 0,
            "has_narratives": len(self.narratives) > 0,
            "case_metadata_set": bool(self.case_title and self.case_summary),
        }

        passed = sum(checks.values())
        total = len(checks)
        score = int((passed / total) * 100) if total else 0

        gaps: list[str] = []
        if not checks["two_plus_actors"]:
            gaps.append("Need at least 2 actors to map the conflict.")
        for actor in self.actors:
            if actor.id not in actors_with_claims:
                gaps.append(f"Actor '{actor.name}' has no claims — what are they asking for or accusing?")
            if actor.id not in actors_with_interests:
                gaps.append(f"Actor '{actor.name}' has no interests — what do they really need?")
            if actor.id not in actors_with_narratives:
                gaps.append(f"Actor '{actor.name}' has no narrative — how do they frame the situation?")
        if not checks["has_constraints"]:
            gaps.append("No constraints identified — are there legal, financial, or time limits?")
        if not checks["has_leverage"]:
            gaps.append("No leverage mapped — who holds power and how?")
        if not checks["has_events"]:
            gaps.append("No events recorded — what happened and when?")
        if not checks["case_metadata_set"]:
            gaps.append("Case title and summary not set.")

        return {
            "score": score,
            "checks": checks,
            "gaps": gaps,
            "ready": score >= 75,
        }

    def find_common_ground(self) -> dict:
        """Analyze shared interests, broken commitments, and leverage balance."""
        # Shared interests: group by interest_type, find types held by multiple actors
        interest_by_type: dict[str, list[dict]] = {}
        for interest in self.interests:
            actor_name = next(
                (a.name for a in self.actors if a.id == interest.actor_id), interest.actor_id
            )
            entry = {"actor": actor_name, "description": interest.description, "priority": interest.priority}
            interest_by_type.setdefault(interest.interest_type, []).append(entry)

        shared_interests = {
            k: v for k, v in interest_by_type.items() if len({e["actor"] for e in v}) >= 2
        }

        # Broken commitments
        broken = []
        for c in self.commitments:
            if c.status == CommitmentStatus.BROKEN:
                from_name = next(
                    (a.name for a in self.actors if a.id == c.committed_actor_id), c.committed_actor_id
                )
                to_name = next(
                    (a.name for a in self.actors if a.id == c.to_actor_id), c.to_actor_id
                )
                broken.append({"description": c.description, "from": from_name, "to": to_name})

        # Leverage balance
        leverage_balance: dict[str, dict] = {}
        for lev in self.leverages:
            holder = next(
                (a.name for a in self.actors if a.id == lev.held_by_actor_id), lev.held_by_actor_id
            )
            target = next(
                (a.name for a in self.actors if a.id == lev.target_actor_id), lev.target_actor_id
            )
            key = holder
            if key not in leverage_balance:
                leverage_balance[key] = {"total_strength": 0, "targets": []}
            leverage_balance[key]["total_strength"] += lev.strength
            leverage_balance[key]["targets"].append(
                {"target": target, "type": lev.leverage_type, "strength": lev.strength}
            )

        return {
            "shared_interests": shared_interests,
            "broken_commitments": broken,
            "leverage_balance": leverage_balance,
        }


# ── Module-level state ──────────────────────────────────────────────────────

graph = ConflictGraph()
active_party: str = "default"
