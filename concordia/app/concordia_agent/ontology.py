"""
CONCORDIA Conflict Ontology

8 structural primitives that decompose any human dispute,
derived from UN Security Council mediation practice.
"""

from __future__ import annotations

import asyncio
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

    parties: list[str] = Field(default_factory=list)

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

    def per_party_health_check(self, party_id: str) -> dict:
        """Score completeness for a single party's contributions.

        Filters all nodes by contributed_by == party_id, then checks
        whether this party has provided sufficient data.
        """
        party_actors = [a for a in self.actors if a.contributed_by == party_id]
        party_claims = [c for c in self.claims if c.contributed_by == party_id]
        party_interests = [i for i in self.interests if i.contributed_by == party_id]
        party_constraints = [c for c in self.constraints if c.contributed_by == party_id]
        party_leverages = [l for l in self.leverages if l.contributed_by == party_id]
        party_events = [e for e in self.events if e.contributed_by == party_id]
        party_narratives = [n for n in self.narratives if n.contributed_by == party_id]

        actor_ids = {a.id for a in party_actors}
        actors_with_claims = {c.source_actor_id for c in party_claims} & actor_ids
        actors_with_interests = {i.actor_id for i in party_interests} & actor_ids

        checks = {
            "has_actors": len(party_actors) >= 1,
            "has_claims": len(party_claims) >= 1,
            "has_interests": len(party_interests) >= 1,
            "has_constraints": len(party_constraints) >= 1,
            "has_events": len(party_events) >= 1,
            "has_narratives": len(party_narratives) >= 1,
        }

        passed = sum(checks.values())
        total = len(checks)
        score = int((passed / total) * 100) if total else 0

        gaps: list[str] = []
        if not checks["has_actors"]:
            gaps.append("No actors identified from this party's input.")
        if not checks["has_claims"]:
            gaps.append("No claims captured — what does this party want or allege?")
        if not checks["has_interests"]:
            gaps.append("No underlying interests found — what really matters to them?")
        if not checks["has_constraints"]:
            gaps.append("No constraints mentioned — any limits or boundaries?")
        if not checks["has_events"]:
            gaps.append("No timeline events — what happened?")
        if not checks["has_narratives"]:
            gaps.append("No narrative captured — how do they see the situation?")

        return {
            "party_id": party_id,
            "score": score,
            "checks": checks,
            "gaps": gaps,
            "counts": {
                "actors": len(party_actors),
                "claims": len(party_claims),
                "interests": len(party_interests),
                "constraints": len(party_constraints),
                "leverages": len(party_leverages),
                "events": len(party_events),
                "narratives": len(party_narratives),
            },
        }

    def escalation_assessment(self) -> EscalationLevel:
        """Compute and update escalation_level based on graph data.

        Uses Glasl-inspired indicators:
        - Accusation/grievance density
        - Broken commitments
        - Leverage asymmetry
        - Adversarial narrative framing
        """
        score = 0

        # Accusation and grievance density
        adversarial_claims = sum(
            1 for c in self.claims
            if c.claim_type in (ClaimType.ACCUSATION, ClaimType.GRIEVANCE)
        )
        proposal_claims = sum(
            1 for c in self.claims if c.claim_type == ClaimType.PROPOSAL
        )
        if adversarial_claims > 0:
            ratio = adversarial_claims / max(len(self.claims), 1)
            if ratio > 0.7:
                score += 3
            elif ratio > 0.4:
                score += 2
            else:
                score += 1

        # Broken commitments
        broken = sum(1 for c in self.commitments if c.status == CommitmentStatus.BROKEN)
        if broken >= 3:
            score += 3
        elif broken >= 1:
            score += 2

        # Leverage asymmetry
        leverage_by_holder: dict[str, int] = {}
        for lev in self.leverages:
            leverage_by_holder.setdefault(lev.held_by_actor_id, 0)
            leverage_by_holder[lev.held_by_actor_id] = (
                leverage_by_holder[lev.held_by_actor_id] + lev.strength
            )
        if leverage_by_holder:
            strengths = list(leverage_by_holder.values())
            if len(strengths) >= 2:
                asymmetry = max(strengths) / max(min(strengths), 1)
                if asymmetry > 3:
                    score += 2
                elif asymmetry > 1.5:
                    score += 1

        # Adversarial narrative framing
        adversarial_frames = {"victim", "betrayal", "villain", "enemy", "aggressor", "threat", "war"}
        frame_hits = 0
        for n in self.narratives:
            for f in n.frames:
                if f.lower() in adversarial_frames:
                    frame_hits += 1
        if frame_hits >= 4:
            score += 3
        elif frame_hits >= 2:
            score += 2
        elif frame_hits >= 1:
            score += 1

        # Map score to level
        if score >= 9:
            level = EscalationLevel.DESTRUCTIVE
        elif score >= 7:
            level = EscalationLevel.CRISIS
        elif score >= 4:
            level = EscalationLevel.ESCALATING
        elif score >= 2:
            level = EscalationLevel.EMERGING
        else:
            level = EscalationLevel.LATENT

        self.escalation_level = level
        return level

    def graph_summary_for_agent(self) -> str:
        """Return a concise text summary suitable for injecting into agent context."""
        lines = []

        if self.case_title:
            lines.append(f"Case: {self.case_title}")
        if self.case_summary:
            lines.append(f"Summary: {self.case_summary}")
        lines.append(f"Escalation: {self.escalation_level}")
        lines.append(f"Phase: {self.phase}")
        lines.append("")

        # Actors
        if self.actors:
            lines.append("ACTORS:")
            for a in self.actors:
                lines.append(f"  - {a.name} ({a.actor_type}) [{a.id}]: {a.role_in_conflict}")
            lines.append("")

        # Claims per actor
        if self.claims:
            lines.append("KEY CLAIMS:")
            claims_by_actor: dict[str, list[str]] = {}
            for c in self.claims:
                actor_name = next(
                    (a.name for a in self.actors if a.id == c.source_actor_id),
                    c.source_actor_id,
                )
                claims_by_actor.setdefault(actor_name, []).append(
                    f"{c.claim_type}: {c.content[:80]}"
                )
            for actor_name, claims in claims_by_actor.items():
                lines.append(f"  {actor_name}:")
                for cl in claims[:3]:  # Limit to 3 per actor for brevity
                    lines.append(f"    - {cl}")
            lines.append("")

        # Shared interests
        common = self.find_common_ground()
        if common["shared_interests"]:
            lines.append("SHARED INTERESTS:")
            for itype, entries in common["shared_interests"].items():
                actors = ", ".join(e["actor"] for e in entries)
                lines.append(f"  - {itype}: shared by {actors}")
            lines.append("")

        # Gaps from health check
        health = self.health_check()
        if health["gaps"]:
            lines.append(f"GAPS (health score: {health['score']}%):")
            for gap in health["gaps"][:5]:
                lines.append(f"  - {gap}")

        return "\n".join(lines)

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

# Thread safety lock for graph mutations
graph_lock = asyncio.Lock()
