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


def add_psychological_profile(
    actor_id: str,
    primary_driver: str,
    secondary_driver: str,
    communication_style: str,
    risk_tolerance: str,
    emotional_state: str,
    notes: str,
) -> dict:
    """Record psychological and motivational indicators for a party.
    Call this when you detect what truly drives someone — is it money, recognition,
    security, control, fairness, relationships, or autonomy?

    This helps the mediator understand negotiation dynamics and craft solutions
    that resonate with each party's core motivations.

    Args:
        actor_id: ID of the actor this profile describes.
        primary_driver: Main motivation. One of: money, recognition, security, control, fairness, relationships, autonomy, legacy, reputation, principle.
        secondary_driver: Secondary motivation (same options as primary_driver).
        communication_style: One of: analytical, emotional, assertive, collaborative, avoidant.
        risk_tolerance: One of: risk_averse, moderate, risk_seeking.
        emotional_state: One of: calm, frustrated, angry, anxious, resigned, hopeful, defensive.
        notes: Free-text observations about their psychology and what matters to them.

    Returns:
        dict confirming the profile was recorded.
    """
    graph = _graph()
    profile = {
        "actor_id": actor_id,
        "primary_driver": primary_driver,
        "secondary_driver": secondary_driver,
        "communication_style": communication_style,
        "risk_tolerance": risk_tolerance,
        "emotional_state": emotional_state,
        "notes": notes,
        "contributed_by": _party(),
    }
    # Store profiles on the graph as a dynamic attribute
    if not hasattr(graph, '_psych_profiles'):
        object.__setattr__(graph, '_psych_profiles', {})
    graph._psych_profiles[actor_id] = profile
    return {"status": "recorded", "actor_id": actor_id, "primary_driver": primary_driver}


def get_missing_ontology_items() -> dict:
    """Analyze the conflict graph and return a structured list of what's missing,
    organized by ontology category, with suggested questions to ask.

    This tool helps the AI lead the conversation by identifying specific gaps
    and providing ready-made questions to fill them.

    Returns:
        dict with missing items per category and suggested questions.
    """
    graph = _graph()
    health = graph.health_check()
    actor_ids = {a.id for a in graph.actors}
    actors_with_claims = {c.source_actor_id for c in graph.claims} & actor_ids
    actors_with_interests = {i.actor_id for i in graph.interests} & actor_ids
    actors_with_narratives = {n.held_by_actor_id for n in graph.narratives} & actor_ids

    missing = {
        "actors_needing_claims": [],
        "actors_needing_interests": [],
        "actors_needing_narratives": [],
        "missing_constraints": not graph.constraints,
        "missing_leverage": not graph.leverages,
        "missing_events": not graph.events,
        "missing_case_info": not (graph.case_title and graph.case_summary),
        "suggested_questions": [],
    }

    for actor in graph.actors:
        if actor.id not in actors_with_claims:
            missing["actors_needing_claims"].append({"id": actor.id, "name": actor.name})
            missing["suggested_questions"].append(
                f"What is {actor.name} asking for or claiming in this situation?"
            )
        if actor.id not in actors_with_interests:
            missing["actors_needing_interests"].append({"id": actor.id, "name": actor.name})
            missing["suggested_questions"].append(
                f"What does {actor.name} really need deep down? What's driving them — is it about money, principle, security, recognition?"
            )
        if actor.id not in actors_with_narratives:
            missing["actors_needing_narratives"].append({"id": actor.id, "name": actor.name})
            missing["suggested_questions"].append(
                f"How does {actor.name} see this situation? Do they feel like the victim, the wronged party, or something else?"
            )

    if not graph.constraints:
        missing["suggested_questions"].append(
            "Are there any deadlines, legal limits, financial caps, or other constraints shaping this situation?"
        )
    if not graph.leverages:
        missing["suggested_questions"].append(
            "Who has power or leverage here? Can either side force the other's hand somehow?"
        )
    if not graph.events:
        missing["suggested_questions"].append(
            "Walk me through what happened. What was the first thing that went wrong, and how did things develop from there?"
        )
    if not (graph.case_title and graph.case_summary):
        missing["suggested_questions"].append(
            "Let me make sure I understand the situation. Can you give me a one-sentence summary of what this conflict is about?"
        )

    # Psychological profiling gaps
    psych_profiles = getattr(graph, '_psych_profiles', {})
    for actor in graph.actors:
        if actor.id not in psych_profiles:
            missing["suggested_questions"].append(
                f"What matters most to {actor.name} in resolving this — money? being heard? fairness? their reputation?"
            )

    missing["health_score"] = health["score"]
    missing["ready"] = health["ready"]
    missing["total_gaps"] = len(missing["suggested_questions"])

    return missing


def get_mediation_roadmap() -> dict:
    """Generate a structured mediation roadmap based on current graph state.
    Identifies available resolution paths, red flags, common ground,
    and recommended next steps for both parties.

    Returns:
        dict with resolution paths, red flags, common ground, and recommendations.
    """
    graph = _graph()
    common = graph.find_common_ground()
    health = graph.health_check()
    escalation = graph.escalation_assessment()
    psych_profiles = getattr(graph, '_psych_profiles', {})

    # Identify red flags
    red_flags = []
    broken_commitments = common.get("broken_commitments", [])
    if broken_commitments:
        red_flags.append(f"{len(broken_commitments)} broken commitment(s) — trust repair needed before agreements work.")
    if escalation in (EscalationLevel.CRISIS, EscalationLevel.DESTRUCTIVE):
        red_flags.append(f"Escalation level is {escalation} — de-escalation should be the first priority.")

    # Check for coercive leverage
    coercive = [l for l in graph.leverages if l.leverage_type == LeverageType.COERCIVE]
    if coercive:
        red_flags.append(f"{len(coercive)} coercive leverage point(s) detected — power imbalance may undermine fair negotiation.")

    # Accusation-heavy claims
    accusations = [c for c in graph.claims if c.claim_type == ClaimType.ACCUSATION]
    if len(accusations) > len(graph.claims) * 0.5 and graph.claims:
        red_flags.append("High accusation density — parties may be more focused on blame than resolution.")

    # Resolution approach recommendations
    resolution_approaches = []

    if common.get("shared_interests"):
        shared_types = list(common["shared_interests"].keys())
        resolution_approaches.append({
            "name": "Interest-Based Negotiation",
            "description": f"Both parties share interests in: {', '.join(shared_types)}. Build agreement from shared ground outward.",
            "suitability": "high",
        })

    if graph.constraints:
        resolution_approaches.append({
            "name": "Constraint-Bounded Resolution",
            "description": "Use existing constraints (legal, financial, temporal) as guardrails to narrow the solution space.",
            "suitability": "medium" if graph.constraints else "low",
        })

    proposals = [c for c in graph.claims if c.claim_type == ClaimType.PROPOSAL]
    if proposals:
        resolution_approaches.append({
            "name": "Proposal Refinement",
            "description": f"{len(proposals)} proposal(s) already on the table. Refine and negotiate from existing offers.",
            "suitability": "high",
        })

    if broken_commitments:
        resolution_approaches.append({
            "name": "Trust Restoration Protocol",
            "description": "Address broken commitments first. Acknowledge harm, establish accountability, then rebuild with small verifiable steps.",
            "suitability": "high" if broken_commitments else "low",
        })

    # Always include a structured dialogue option
    resolution_approaches.append({
        "name": "Structured Dialogue",
        "description": "Guided conversation: each party states their core need (2 min), then shared concerns are identified, then joint brainstorming.",
        "suitability": "medium",
    })

    # Party-specific recommendations
    party_recommendations = {}
    for actor in graph.actors:
        profile = psych_profiles.get(actor.id, {})
        recs = []
        driver = profile.get("primary_driver", "unknown")
        if driver == "money":
            recs.append("Frame solutions in financial terms. Quantify costs of continued conflict vs. settlement.")
        elif driver == "recognition":
            recs.append("Ensure they feel heard and acknowledged. Public validation of their concerns may be key.")
        elif driver == "fairness":
            recs.append("Appeal to process fairness. Transparent, rule-based approaches will resonate.")
        elif driver == "security":
            recs.append("Offer guarantees, documentation, and fallback protections. Reduce uncertainty.")
        elif driver == "control":
            recs.append("Give them choices and agency in the process. Avoid presenting ultimatums.")
        elif driver == "relationships":
            recs.append("Emphasize the relationship's future value. Explore collaborative frameworks.")
        elif driver == "reputation":
            recs.append("Frame resolution as reputation-enhancing. Show how agreement looks stronger than conflict.")
        else:
            recs.append("Explore what truly drives this party — their core motivation is not yet clear.")

        emotional = profile.get("emotional_state", "unknown")
        if emotional in ("angry", "frustrated", "defensive"):
            recs.append(f"Party is currently {emotional} — allow venting time and validate feelings before problem-solving.")
        elif emotional == "anxious":
            recs.append("Party is anxious — provide clear process structure and timeline to reduce uncertainty.")

        party_recommendations[actor.name] = recs

    return {
        "health_score": health["score"],
        "escalation_level": str(escalation),
        "red_flags": red_flags,
        "common_ground": common.get("shared_interests", {}),
        "resolution_approaches": resolution_approaches,
        "party_recommendations": party_recommendations,
        "next_steps": [
            "Review red flags and address any power imbalances",
            "Present shared interests to both parties as foundation for agreement",
            "Guide parties through resolution approaches in order of suitability",
            "Draft concrete agreement terms referencing specific interests and constraints",
        ],
    }


# ── Tool lists for agent assignment ──────────────────────────────────────────

LISTENER_TOOLS = [
    add_actor, add_claim, add_interest, add_constraint,
    add_leverage, add_commitment, add_event, add_narrative,
    add_edge, set_case_info, ingest_document,
    add_psychological_profile, get_missing_ontology_items,
]

ANALYZER_TOOLS = [
    get_graph, run_health_check, analyze_common_ground,
    get_missing_ontology_items, get_mediation_roadmap,
]
