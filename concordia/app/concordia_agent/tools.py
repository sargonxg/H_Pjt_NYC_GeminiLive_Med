"""
CONCORDIA Agent Tools

14 tool functions that Gemini calls during mediation conversations
to build, analyze, and resolve the conflict knowledge graph.

Tools read `graph` and `active_party` from the ontology module dynamically
so that multi-party / multi-case code can swap the active graph at runtime.
"""

from __future__ import annotations

from . import ontology
from .ontology import (
    Actor, ActorType, Claim, ClaimType, Interest, InterestType,
    Constraint, ConstraintType, Leverage, LeverageType,
    Commitment, CommitmentStatus, Event, EventType,
    Narrative, Edge, Document, EscalationLevel, Phase,
)


def _graph():
    """Get the current active graph (allows runtime swapping)."""
    return ontology.graph


def _party():
    """Get the current active party (allows runtime swapping)."""
    return ontology.active_party


# ── Graph Building Tools (Listener) ─────────────────────────────────────────

def add_actor(name: str, actor_type: str, description: str, role_in_conflict: str) -> dict:
    """Add a person, group, or organization involved in the conflict.
    Call this when someone mentions a name or party in the dispute.
    Deduplicates by name — safe to call multiple times for the same person.

    Args:
        name: Full name or label of the actor (e.g. "Maria", "Acme Corp").
        actor_type: One of: individual, organization, state, group, institution.
        description: Brief description of who they are.
        role_in_conflict: Their role (e.g. "complainant", "landlord", "mediator").

    Returns:
        dict with the actor id, name, and whether it was newly created.
    """
    graph = _graph()
    # Deduplicate by name
    for existing in graph.actors:
        if existing.name.lower() == name.lower():
            return {"id": existing.id, "name": existing.name, "status": "already_exists"}

    actor = Actor(
        name=name,
        actor_type=ActorType(actor_type),
        description=description,
        role_in_conflict=role_in_conflict,
        contributed_by=_party(),
    )
    graph.actors.append(actor)
    graph.phase = Phase.STRUCTURE
    return {"id": actor.id, "name": actor.name, "status": "created"}


def add_claim(claim_type: str, content: str, source_actor_id: str, target_actor_id: str) -> dict:
    """Record a demand, accusation, grievance, justification, or proposal made by one party
    about or toward another. Call this when someone states what they want, what went wrong,
    or what they accuse the other side of.

    Args:
        claim_type: One of: demand, accusation, justification, proposal, grievance.
        content: The substance of the claim in the speaker's own words.
        source_actor_id: ID of the actor making the claim.
        target_actor_id: ID of the actor the claim is directed at (can be empty).

    Returns:
        dict with the claim id and edges created.
    """
    graph = _graph()
    claim = Claim(
        claim_type=ClaimType(claim_type),
        content=content,
        source_actor_id=source_actor_id,
        target_actor_id=target_actor_id,
        contributed_by=_party(),
    )
    graph.claims.append(claim)

    edges_created = []
    graph.edges.append(Edge(
        source_id=source_actor_id, target_id=claim.id,
        relationship="MAKES_CLAIM", description=f"Makes {claim_type}: {content[:60]}",
    ))
    edges_created.append("MAKES_CLAIM")

    if target_actor_id:
        graph.edges.append(Edge(
            source_id=claim.id, target_id=target_actor_id,
            relationship="CLAIM_TARGETS", description=f"Claim targets actor",
        ))
        edges_created.append("CLAIM_TARGETS")

    return {"id": claim.id, "edges": edges_created}


def add_interest(interest_type: str, description: str, actor_id: str, priority: int) -> dict:
    """Record a deeper need or motivation behind a party's position.
    Call this when you uncover WHY someone wants something — their underlying
    security, economic, identity, autonomy, recognition, or procedural need.

    Args:
        interest_type: One of: security, economic, identity, autonomy, recognition, procedural.
        description: What the underlying interest or need is.
        actor_id: ID of the actor who holds this interest.
        priority: Importance from 1 (low) to 5 (critical).

    Returns:
        dict with the interest id.
    """
    graph = _graph()
    interest = Interest(
        interest_type=InterestType(interest_type),
        description=description,
        actor_id=actor_id,
        priority=priority,
        contributed_by=_party(),
    )
    graph.interests.append(interest)
    graph.edges.append(Edge(
        source_id=actor_id, target_id=interest.id,
        relationship="HAS_INTEREST", description=f"Has {interest_type} interest: {description[:60]}",
    ))
    return {"id": interest.id}


def add_constraint(constraint_type: str, description: str, affects_actor_ids: str) -> dict:
    """Record a limit or boundary that shapes what is possible in this conflict.
    Call this when someone mentions deadlines, legal limits, budget caps,
    cultural norms, or structural barriers.

    Args:
        constraint_type: One of: legal, financial, temporal, normative, structural, relational.
        description: What the constraint is.
        affects_actor_ids: Comma-separated actor IDs affected by this constraint.

    Returns:
        dict with the constraint id and edges created.
    """
    graph = _graph()
    ids = [aid.strip() for aid in affects_actor_ids.split(",") if aid.strip()]
    constraint = Constraint(
        constraint_type=ConstraintType(constraint_type),
        description=description,
        affects_actor_ids=ids,
        contributed_by=_party(),
    )
    graph.constraints.append(constraint)

    for aid in ids:
        graph.edges.append(Edge(
            source_id=constraint.id, target_id=aid,
            relationship="CONSTRAINS", description=f"Constrains actor",
        ))
    return {"id": constraint.id, "edges_created": len(ids)}


def add_leverage(leverage_type: str, description: str, held_by_actor_id: str,
                 target_actor_id: str, strength: int) -> dict:
    """Record a source of power or influence one party holds over another.
    Call this when someone describes power dynamics, threats, incentives,
    information advantages, or relationship-based influence.

    Args:
        leverage_type: One of: coercive, reward, informational, normative, relational, structural.
        description: What the leverage is and how it works.
        held_by_actor_id: ID of the actor who holds this leverage.
        target_actor_id: ID of the actor this leverage is used against.
        strength: Power level from 1 (weak) to 5 (dominant).

    Returns:
        dict with the leverage id.
    """
    graph = _graph()
    leverage = Leverage(
        leverage_type=LeverageType(leverage_type),
        description=description,
        held_by_actor_id=held_by_actor_id,
        target_actor_id=target_actor_id,
        strength=strength,
        contributed_by=_party(),
    )
    graph.leverages.append(leverage)
    graph.edges.append(Edge(
        source_id=held_by_actor_id, target_id=leverage.id,
        relationship="HOLDS_LEVERAGE", description=f"Holds {leverage_type} leverage",
    ))
    graph.edges.append(Edge(
        source_id=leverage.id, target_id=target_actor_id,
        relationship="LEVERAGE_OVER", description=f"Leverage over actor",
    ))
    return {"id": leverage.id}


def add_commitment(description: str, committed_actor_id: str, to_actor_id: str, status: str) -> dict:
    """Record a promise, agreement, or obligation between parties.
    Call this when someone mentions a promise made, a deal struck,
    or an obligation — whether kept, broken, or still active.

    Args:
        description: What was promised or agreed to.
        committed_actor_id: ID of the actor who made the commitment.
        to_actor_id: ID of the actor the commitment was made to.
        status: One of: active, broken, fulfilled.

    Returns:
        dict with the commitment id.
    """
    graph = _graph()
    commitment = Commitment(
        description=description,
        committed_actor_id=committed_actor_id,
        to_actor_id=to_actor_id,
        status=CommitmentStatus(status),
        contributed_by=_party(),
    )
    graph.commitments.append(commitment)
    graph.edges.append(Edge(
        source_id=committed_actor_id, target_id=commitment.id,
        relationship="COMMITTED_TO", description=f"Committed: {description[:60]}",
    ))
    return {"id": commitment.id}


def add_event(event_type: str, description: str, date: str, involved_actor_ids: str) -> dict:
    """Record a significant event in the conflict timeline.
    Call this when someone describes something that happened — a trigger,
    escalation, de-escalation, negotiation attempt, agreement, or violation.

    Args:
        event_type: One of: trigger, escalation, de_escalation, negotiation, agreement, violation.
        description: What happened.
        date: When it happened (any format, e.g. "last Tuesday", "2024-01-15").
        involved_actor_ids: Comma-separated actor IDs involved in this event.

    Returns:
        dict with the event id.
    """
    graph = _graph()
    ids = [aid.strip() for aid in involved_actor_ids.split(",") if aid.strip()]
    event = Event(
        event_type=EventType(event_type),
        description=description,
        date=date,
        involved_actor_ids=ids,
        contributed_by=_party(),
    )
    graph.events.append(event)

    for aid in ids:
        graph.edges.append(Edge(
            source_id=aid, target_id=event.id,
            relationship="INVOLVED_IN", description=f"Involved in event",
        ))
    return {"id": event.id}


def add_narrative(description: str, held_by_actor_id: str, frames: str) -> dict:
    """Record how a party frames or tells the story of the conflict.
    Call this when you notice someone casting themselves or others in a role
    (victim, villain, hero), or using particular framing language.

    Args:
        description: Summary of their narrative or worldview about the conflict.
        held_by_actor_id: ID of the actor who holds this narrative.
        frames: Comma-separated frame labels (e.g. "victim, betrayal, justice").

    Returns:
        dict with the narrative id.
    """
    graph = _graph()
    frame_list = [f.strip() for f in frames.split(",") if f.strip()]
    narrative = Narrative(
        description=description,
        held_by_actor_id=held_by_actor_id,
        frames=frame_list,
        contributed_by=_party(),
    )
    graph.narratives.append(narrative)
    graph.edges.append(Edge(
        source_id=held_by_actor_id, target_id=narrative.id,
        relationship="HOLDS_NARRATIVE", description=f"Holds narrative: {description[:60]}",
    ))
    return {"id": narrative.id}


def add_edge(source_id: str, target_id: str, relationship: str, description: str) -> dict:
    """Create a custom relationship between any two nodes in the conflict graph.
    Use this for relationships not automatically created by other tools.

    Args:
        source_id: ID of the source node.
        target_id: ID of the target node.
        relationship: Relationship label (e.g. "ALLIES_WITH", "OPPOSES").
        description: Brief description of the relationship.

    Returns:
        dict confirming the edge was created.
    """
    graph = _graph()
    edge = Edge(
        source_id=source_id,
        target_id=target_id,
        relationship=relationship,
        description=description,
    )
    graph.edges.append(edge)
    return {"status": "created", "relationship": relationship}


def set_case_info(case_title: str, case_summary: str, escalation_level: str) -> dict:
    """Set the overall case title, summary, and escalation level.
    Call this once you have enough context to name and summarize the dispute.

    Args:
        case_title: Short title for the case (e.g. "Chen-Martinez Lease Dispute").
        case_summary: One-paragraph summary of the conflict.
        escalation_level: One of: latent, emerging, escalating, crisis, destructive.

    Returns:
        dict confirming the case info was set.
    """
    graph = _graph()
    graph.case_title = case_title
    graph.case_summary = case_summary
    graph.escalation_level = EscalationLevel(escalation_level)
    return {"status": "set", "title": case_title, "escalation": escalation_level}


def ingest_document(text: str, name: str) -> dict:
    """Ingest a document (contract, email, letter, etc.) that a party shares.
    Records metadata and returns the text for you to analyze and extract
    actors, claims, events, and other primitives from.

    Args:
        text: The full text content of the document.
        name: A label for the document (e.g. "Lease Agreement", "Email from Jan 5").

    Returns:
        dict with document metadata and the text to analyze.
    """
    graph = _graph()
    doc = Document(name=name, length=len(text), contributed_by=_party())
    graph.documents.append(doc)
    return {
        "status": "ingested",
        "name": name,
        "length": len(text),
        "instruction": "Analyze this document and extract actors, claims, events, constraints, and other conflict primitives.",
        "content": text,
    }


# ── Analysis Tools (Verifier & Resolver) ────────────────────────────────────

def get_graph() -> dict:
    """Get the complete current state of the conflict knowledge graph,
    including all actors, claims, interests, constraints, leverage,
    commitments, events, narratives, edges, and a health check.

    Returns:
        dict with the full graph data and health check results.
    """
    graph = _graph()
    data = graph.model_dump()
    data["health"] = graph.health_check()
    return data


def run_health_check() -> dict:
    """Evaluate whether the conflict graph is complete enough for resolution.
    Sets the phase to VERIFY and returns a detailed health assessment
    with score, checks, gaps, and readiness status.

    Returns:
        dict with score (0-100), checks, gaps, and ready boolean.
    """
    graph = _graph()
    graph.phase = Phase.VERIFY
    result = graph.health_check()
    # Also update escalation assessment
    graph.escalation_assessment()
    return result


def analyze_common_ground() -> dict:
    """Analyze the conflict graph to find resolution opportunities.
    Sets the phase to RESOLVE and returns shared interests across parties,
    broken commitments that need repair, and leverage balance.

    Returns:
        dict with shared_interests, broken_commitments, and leverage_balance.
    """
    graph = _graph()
    graph.phase = Phase.RESOLVE
    return graph.find_common_ground()


# ── Tool lists for agent assignment ──────────────────────────────────────────

LISTENER_TOOLS = [
    add_actor, add_claim, add_interest, add_constraint,
    add_leverage, add_commitment, add_event, add_narrative,
    add_edge, set_case_info, ingest_document,
]

ANALYZER_TOOLS = [
    get_graph, run_health_check, analyze_common_ground,
]
