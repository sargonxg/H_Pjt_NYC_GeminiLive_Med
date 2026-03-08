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


# ── Mediation / Conflict Resolution Theoretical Frameworks ───────────────────

def assess_fisher_ury() -> dict:
    """Apply Fisher & Ury's principled negotiation framework (Getting to Yes).

    Evaluates the current conflict graph against the four pillars of
    interest-based negotiation:
      1. Separate the people from the problem
      2. Focus on interests, not positions
      3. Generate options for mutual gain
      4. Insist on objective criteria

    Returns:
        dict with a score (0-10) for each principle, an overall score,
        narrative explanations, and actionable recommendations.
    """
    graph = _graph()

    # --- 1. People vs Problem ---------------------------------------------------
    accusations = [c for c in graph.claims if c.claim_type == ClaimType.ACCUSATION]
    grievances = [c for c in graph.claims if c.claim_type == ClaimType.GRIEVANCE]
    personal_attack_count = len(accusations) + len(grievances)
    total_claims = max(len(graph.claims), 1)
    personal_ratio = personal_attack_count / total_claims
    people_problem_score = round(max(0, 10 - personal_ratio * 10), 1)
    people_problem_notes = (
        "High proportion of accusations/grievances suggests parties conflate "
        "the person with the problem."
        if personal_ratio > 0.5
        else "Parties appear reasonably able to separate personal feelings from substantive issues."
    )

    # --- 2. Interests vs Positions ----------------------------------------------
    interests_count = len(graph.interests)
    demands = [c for c in graph.claims if c.claim_type == ClaimType.DEMAND]
    interest_to_demand = interests_count / max(len(demands), 1)
    interests_score = round(min(10, interest_to_demand * 5), 1)
    interests_notes = (
        "Underlying interests are well-explored relative to positional demands."
        if interests_score >= 6
        else "More work is needed to uncover interests behind stated positions."
    )

    # --- 3. Options for Mutual Gain ---------------------------------------------
    proposals = [c for c in graph.claims if c.claim_type == ClaimType.PROPOSAL]
    common = graph.find_common_ground()
    shared_interests = common.get("shared_interests", {})
    options_score = round(min(10, len(proposals) * 2.5 + len(shared_interests) * 2), 1)
    options_notes = (
        f"{len(proposals)} proposal(s) on the table and {len(shared_interests)} "
        f"shared interest area(s) identified."
    )

    # --- 4. Objective Criteria --------------------------------------------------
    constraints = graph.constraints
    legal = [c for c in constraints if c.constraint_type == ConstraintType.LEGAL]
    financial = [c for c in constraints if c.constraint_type == ConstraintType.FINANCIAL]
    criteria_score = round(min(10, (len(legal) + len(financial)) * 2.5 + len(constraints) * 1), 1)
    criteria_notes = (
        f"{len(constraints)} constraint(s) recorded ({len(legal)} legal, "
        f"{len(financial)} financial) that can serve as objective criteria."
    )

    overall = round((people_problem_score + interests_score + options_score + criteria_score) / 4, 1)

    recommendations = []
    if people_problem_score < 5:
        recommendations.append(
            "Reframe accusations into shared-problem statements. "
            "Acknowledge emotions but redirect to interests."
        )
    if interests_score < 5:
        recommendations.append(
            "Ask 'why?' and 'why not?' behind each demand to surface underlying interests."
        )
    if options_score < 5:
        recommendations.append(
            "Facilitate brainstorming: generate at least three creative options "
            "before evaluating any of them."
        )
    if criteria_score < 5:
        recommendations.append(
            "Introduce external benchmarks (market rates, legal standards, precedent) "
            "to anchor discussion in objective criteria."
        )

    return {
        "framework": "Fisher & Ury — Getting to Yes",
        "overall_score": overall,
        "principles": {
            "separate_people_from_problem": {
                "score": people_problem_score,
                "notes": people_problem_notes,
            },
            "focus_on_interests": {
                "score": interests_score,
                "notes": interests_notes,
            },
            "generate_options_for_mutual_gain": {
                "score": options_score,
                "notes": options_notes,
            },
            "use_objective_criteria": {
                "score": criteria_score,
                "notes": criteria_notes,
            },
        },
        "recommendations": recommendations,
    }


def assess_galtung_triangle() -> dict:
    """Apply Johan Galtung's Conflict Triangle (ABC model).

    Analyses the conflict across three interdependent dimensions:
      A — Attitudes: perceptions, stereotypes, emotions held by each party.
      B — Behavior: observable actions, threats, coercion, or cooperation.
      C — Contradictions: incompatible goals or structural issues at the root.

    Returns:
        dict with detailed findings for each dimension and overall assessment.
    """
    graph = _graph()

    # --- A: Attitudes -----------------------------------------------------------
    attitudes = []
    psych_profiles = getattr(graph, '_psych_profiles', {})
    for actor in graph.actors:
        profile = psych_profiles.get(actor.id, {})
        actor_narratives = [n for n in graph.narratives if n.held_by_actor_id == actor.id]
        frames = []
        for n in actor_narratives:
            frames.extend(n.frames)
        attitudes.append({
            "actor": actor.name,
            "emotional_state": profile.get("emotional_state", "unknown"),
            "communication_style": profile.get("communication_style", "unknown"),
            "frames": frames if frames else ["no frames recorded"],
            "narrative_count": len(actor_narratives),
        })

    negative_emotions = {"angry", "frustrated", "defensive"}
    attitude_severity = sum(
        1 for a in attitudes
        if a["emotional_state"] in negative_emotions
    )

    # --- B: Behavior ------------------------------------------------------------
    escalation_events = [e for e in graph.events if e.event_type == EventType.ESCALATION]
    de_escalation_events = [e for e in graph.events if e.event_type == EventType.DE_ESCALATION]
    violations = [e for e in graph.events if e.event_type == EventType.VIOLATION]
    coercive_leverage = [l for l in graph.leverages if l.leverage_type == LeverageType.COERCIVE]
    behavior = {
        "escalation_events": len(escalation_events),
        "de_escalation_events": len(de_escalation_events),
        "violations": len(violations),
        "coercive_leverage_points": len(coercive_leverage),
        "broken_commitments": len([c for c in graph.commitments if c.status == CommitmentStatus.BROKEN]),
        "net_direction": (
            "escalating" if len(escalation_events) > len(de_escalation_events)
            else "de-escalating" if len(de_escalation_events) > len(escalation_events)
            else "stable"
        ),
    }

    # --- C: Contradictions ------------------------------------------------------
    actor_interests: dict[str, list[str]] = {}
    for interest in graph.interests:
        actor_interests.setdefault(interest.actor_id, []).append(interest.description)
    demands_by_actor: dict[str, list[str]] = {}
    for claim in graph.claims:
        if claim.claim_type == ClaimType.DEMAND:
            demands_by_actor.setdefault(claim.source_actor_id, []).append(claim.content)
    structural_constraints = [
        c for c in graph.constraints
        if c.constraint_type in (ConstraintType.STRUCTURAL, ConstraintType.LEGAL)
    ]
    contradictions = {
        "incompatible_demands": demands_by_actor,
        "structural_constraints": [c.description for c in structural_constraints],
        "actors_with_competing_interests": len(actor_interests),
    }

    # Overall assessment
    severity_indicators = attitude_severity + behavior["escalation_events"] + behavior["violations"]
    if severity_indicators >= 5:
        overall = "severe — all three triangle dimensions show significant conflict drivers"
    elif severity_indicators >= 2:
        overall = "moderate — conflict drivers present but manageable with intervention"
    else:
        overall = "mild — early stage with opportunities for prevention"

    return {
        "framework": "Galtung's Conflict Triangle (ABC)",
        "overall_assessment": overall,
        "attitudes": attitudes,
        "behavior": behavior,
        "contradictions": contradictions,
    }


def assess_glasl_escalation() -> dict:
    """Apply Friedrich Glasl's 9-stage conflict escalation model.

    Stages are grouped into three meta-phases:
      Stages 1-3 (Win-Win): Hardening, Debate & Polemics, Actions not Words
      Stages 4-6 (Win-Lose): Coalitions, Loss of Face, Strategies of Threats
      Stages 7-9 (Lose-Lose): Limited Destruction, Fragmentation, Together into the Abyss

    Determines the current stage based on graph indicators and recommends
    appropriate intervention strategies.

    Returns:
        dict with current stage, phase, indicator analysis, and recommendations.
    """
    graph = _graph()

    # Gather indicators
    accusations = [c for c in graph.claims if c.claim_type == ClaimType.ACCUSATION]
    demands = [c for c in graph.claims if c.claim_type == ClaimType.DEMAND]
    proposals = [c for c in graph.claims if c.claim_type == ClaimType.PROPOSAL]
    escalation_events = [e for e in graph.events if e.event_type == EventType.ESCALATION]
    violations = [e for e in graph.events if e.event_type == EventType.VIOLATION]
    coercive_leverage = [l for l in graph.leverages if l.leverage_type == LeverageType.COERCIVE]
    broken_commitments = [c for c in graph.commitments if c.status == CommitmentStatus.BROKEN]

    psych_profiles = getattr(graph, '_psych_profiles', {})
    angry_parties = sum(
        1 for p in psych_profiles.values()
        if p.get("emotional_state") in ("angry", "defensive")
    )

    # Heuristic scoring to estimate the stage
    score = 0
    indicators = []

    # Stage 1-2 indicators: positions harden, debate intensifies
    if len(demands) >= 1:
        score += 1
        indicators.append("Hardened positions detected (demands present)")
    if len(accusations) >= 1:
        score += 1
        indicators.append("Debate/polemics phase: accusations being made")

    # Stage 3: actions replace words
    if len(escalation_events) >= 1:
        score += 1
        indicators.append("Actions not words: escalation events recorded")

    # Stage 4: coalitions and seeking allies
    if len(graph.actors) > 2:
        third_parties = [a for a in graph.actors if a.role_in_conflict not in ("complainant", "respondent", "mediator")]
        if third_parties:
            score += 1
            indicators.append(f"Coalition building: {len(third_parties)} additional actor(s) involved")

    # Stage 5: loss of face
    if angry_parties >= 1:
        score += 1
        indicators.append(f"Loss of face dynamics: {angry_parties} party/parties in angry/defensive state")

    # Stage 6: strategies of threats
    if len(coercive_leverage) >= 1:
        score += 1
        indicators.append(f"Threat strategies: {len(coercive_leverage)} coercive leverage point(s)")

    # Stage 7: limited destruction
    if len(violations) >= 1:
        score += 1
        indicators.append(f"Limited destruction: {len(violations)} violation event(s)")

    # Stage 8-9: fragmentation / total destruction
    if len(broken_commitments) >= 2:
        score += 1
        indicators.append("Fragmentation: multiple broken commitments suggest total breakdown of trust")
    if len(violations) >= 2 and len(coercive_leverage) >= 2:
        score += 1
        indicators.append("Approaching abyss: combined violations and coercion indicate severe escalation")

    # Map score to stage
    stage = min(max(score, 1), 9)

    if stage <= 3:
        phase = "Win-Win"
        phase_description = "Resolution through direct dialogue is still possible."
        recommendations = [
            "Facilitate structured dialogue between parties.",
            "Encourage active listening and perspective-taking.",
            "Help parties move from positions to interests.",
            "A skilled facilitator or moderator may be sufficient.",
        ]
    elif stage <= 6:
        phase = "Win-Lose"
        phase_description = "Parties are competing; one side expects to lose. Professional mediation is needed."
        recommendations = [
            "Engage a professional mediator immediately.",
            "Establish ground rules and safe communication structure.",
            "Address power imbalances before substantive negotiation.",
            "Work on de-escalation before attempting resolution.",
            "Consider separate caucuses (shuttle diplomacy) if face-to-face is too volatile.",
        ]
    else:
        phase = "Lose-Lose"
        phase_description = "Both parties are willing to suffer harm to damage the other. Urgent intervention needed."
        recommendations = [
            "Immediate intervention by authoritative third party required.",
            "Consider arbitration or adjudication rather than mediation.",
            "Safety assessment needed — check for threats of harm.",
            "Separate parties completely; no direct contact.",
            "Engage legal and/or mental health professionals.",
        ]

    return {
        "framework": "Glasl's 9-Stage Escalation Model",
        "estimated_stage": stage,
        "phase": phase,
        "phase_description": phase_description,
        "stage_names": {
            1: "Hardening",
            2: "Debate & Polemics",
            3: "Actions not Words",
            4: "Coalitions",
            5: "Loss of Face",
            6: "Strategies of Threats",
            7: "Limited Destruction",
            8: "Fragmentation",
            9: "Together into the Abyss",
        },
        "indicators_detected": indicators,
        "recommendations": recommendations,
    }


def assess_deutsch_cooperation() -> dict:
    """Apply Morton Deutsch's Cooperation-Competition Theory.

    Evaluates whether parties display a cooperative or competitive
    orientation by examining:
      - Promotive interdependence (goals are positively linked)
      - Contrient interdependence (goals are negatively linked)
      - Communication quality and trust indicators

    Returns:
        dict with cooperation score (-10 to +10), orientation per party,
        interdependence type, and strategy shift recommendations.
    """
    graph = _graph()
    common = graph.find_common_ground()
    psych_profiles = getattr(graph, '_psych_profiles', {})

    # Cooperative signals
    proposals = [c for c in graph.claims if c.claim_type == ClaimType.PROPOSAL]
    shared_interests = common.get("shared_interests", {})
    fulfilled = [c for c in graph.commitments if c.status == CommitmentStatus.FULFILLED]
    de_escalations = [e for e in graph.events if e.event_type == EventType.DE_ESCALATION]
    cooperative_signals = len(proposals) + len(shared_interests) + len(fulfilled) + len(de_escalations)

    # Competitive signals
    accusations = [c for c in graph.claims if c.claim_type == ClaimType.ACCUSATION]
    coercive = [l for l in graph.leverages if l.leverage_type == LeverageType.COERCIVE]
    broken = [c for c in graph.commitments if c.status == CommitmentStatus.BROKEN]
    escalations = [e for e in graph.events if e.event_type == EventType.ESCALATION]
    competitive_signals = len(accusations) + len(coercive) + len(broken) + len(escalations)

    # Score from -10 (purely competitive) to +10 (purely cooperative)
    raw = cooperative_signals - competitive_signals
    cooperation_score = max(-10, min(10, raw))

    if cooperation_score > 3:
        orientation = "cooperative"
        interdependence = "promotive — parties' goals are positively linked"
    elif cooperation_score < -3:
        orientation = "competitive"
        interdependence = "contrient — parties' goals are negatively linked"
    else:
        orientation = "mixed"
        interdependence = "mixed — some goals aligned, some opposed"

    # Per-party orientation
    party_orientations = {}
    for actor in graph.actors:
        actor_proposals = [c for c in proposals if c.source_actor_id == actor.id]
        actor_accusations = [c for c in accusations if c.source_actor_id == actor.id]
        profile = psych_profiles.get(actor.id, {})
        style = profile.get("communication_style", "unknown")
        coop = len(actor_proposals)
        comp = len(actor_accusations)
        if coop > comp:
            party_orientations[actor.name] = "cooperative"
        elif comp > coop:
            party_orientations[actor.name] = "competitive"
        else:
            party_orientations[actor.name] = "neutral / unclear"
        party_orientations[actor.name] += f" (style: {style})"

    recommendations = []
    if orientation == "competitive":
        recommendations.extend([
            "Shift from competitive to cooperative framing: emphasize shared losses from continued conflict.",
            "Introduce reciprocal concessions — small cooperative gestures build momentum.",
            "Reframe the conflict as a shared problem both parties need to solve together.",
            "Highlight areas of promotive interdependence (shared interests) even if small.",
        ])
    elif orientation == "mixed":
        recommendations.extend([
            "Build on existing cooperative elements to shift the overall dynamic.",
            "Address competitive behaviors directly — name the pattern without blame.",
            "Create structured turn-taking to prevent competitive communication spirals.",
        ])
    else:
        recommendations.extend([
            "Maintain cooperative momentum by acknowledging positive moves explicitly.",
            "Transition from interest exploration to joint option generation.",
            "Document agreements incrementally to build confidence.",
        ])

    return {
        "framework": "Deutsch's Cooperation-Competition Theory",
        "cooperation_score": cooperation_score,
        "overall_orientation": orientation,
        "interdependence_type": interdependence,
        "cooperative_signals": cooperative_signals,
        "competitive_signals": competitive_signals,
        "party_orientations": party_orientations,
        "recommendations": recommendations,
    }


def assess_bush_folger_transformation() -> dict:
    """Apply Bush & Folger's Transformative Mediation framework.

    Evaluates two key dimensions for each party:
      - Empowerment: Has the party gained clarity about their own goals,
        options, resources, and decision-making capacity?
      - Recognition: Has the party acknowledged the other side's perspective,
        situation, and humanity?

    Returns:
        dict with empowerment and recognition scores per party (0-10),
        overall transformation assessment, and facilitation suggestions.
    """
    graph = _graph()
    psych_profiles = getattr(graph, '_psych_profiles', {})

    party_assessments = {}
    for actor in graph.actors:
        # --- Empowerment --------------------------------------------------------
        actor_interests = [i for i in graph.interests if i.actor_id == actor.id]
        actor_claims = [c for c in graph.claims if c.source_actor_id == actor.id]
        actor_proposals = [c for c in actor_claims if c.claim_type == ClaimType.PROPOSAL]
        profile = psych_profiles.get(actor.id, {})
        has_profile = bool(profile)

        empowerment_points = 0
        empowerment_notes = []

        if actor_interests:
            empowerment_points += min(3, len(actor_interests))
            empowerment_notes.append(f"{len(actor_interests)} interest(s) articulated")
        else:
            empowerment_notes.append("No interests articulated yet — goals unclear")

        if actor_proposals:
            empowerment_points += min(3, len(actor_proposals))
            empowerment_notes.append(f"{len(actor_proposals)} proposal(s) made — showing agency")
        else:
            empowerment_notes.append("No proposals made — not yet exercising options")

        if has_profile:
            empowerment_points += 2
            empowerment_notes.append("Motivational drivers identified")

        if actor_claims:
            empowerment_points += min(2, len(actor_claims))
            empowerment_notes.append(f"Voice expressed through {len(actor_claims)} claim(s)")

        empowerment_score = min(10, empowerment_points)

        # --- Recognition --------------------------------------------------------
        # Recognition is harder to measure directly; we use proxies:
        # - Did other parties' narratives acknowledge this actor?
        # - Are there proposals that address this actor's interests?
        # - Are there de-escalation events involving this actor?
        other_actors = [a for a in graph.actors if a.id != actor.id]
        recognition_points = 0
        recognition_notes = []

        # Check if other parties made proposals toward this actor
        for other in other_actors:
            other_proposals = [
                c for c in graph.claims
                if c.source_actor_id == other.id
                and c.claim_type == ClaimType.PROPOSAL
                and c.target_actor_id == actor.id
            ]
            if other_proposals:
                recognition_points += min(3, len(other_proposals))
                recognition_notes.append(
                    f"{other.name} made {len(other_proposals)} proposal(s) acknowledging {actor.name}'s concerns"
                )

        # Check for de-escalation events involving this actor
        de_escalations = [
            e for e in graph.events
            if e.event_type == EventType.DE_ESCALATION and actor.id in e.involved_actor_ids
        ]
        if de_escalations:
            recognition_points += min(3, len(de_escalations))
            recognition_notes.append(f"{len(de_escalations)} de-escalation effort(s) involving {actor.name}")

        # Check for fulfilled commitments to this actor
        fulfilled_to = [
            c for c in graph.commitments
            if c.to_actor_id == actor.id and c.status == CommitmentStatus.FULFILLED
        ]
        if fulfilled_to:
            recognition_points += min(2, len(fulfilled_to))
            recognition_notes.append(f"{len(fulfilled_to)} commitment(s) fulfilled toward {actor.name}")

        # Shared interests suggest some recognition
        if graph.find_common_ground().get("shared_interests"):
            recognition_points += 2
            recognition_notes.append("Shared interests identified — some mutual recognition present")

        if not recognition_notes:
            recognition_notes.append("No evidence of recognition from other parties yet")

        recognition_score = min(10, recognition_points)

        party_assessments[actor.name] = {
            "empowerment_score": empowerment_score,
            "empowerment_notes": empowerment_notes,
            "recognition_score": recognition_score,
            "recognition_notes": recognition_notes,
        }

    # Overall assessment
    avg_empowerment = (
        sum(p["empowerment_score"] for p in party_assessments.values()) / max(len(party_assessments), 1)
    )
    avg_recognition = (
        sum(p["recognition_score"] for p in party_assessments.values()) / max(len(party_assessments), 1)
    )

    suggestions = []
    if avg_empowerment < 5:
        suggestions.append(
            "Help parties articulate their own goals, options, and resources. "
            "Ask: 'What matters most to you? What options do you see?'"
        )
    if avg_recognition < 5:
        suggestions.append(
            "Encourage perspective-taking. Ask: 'What do you think the other side "
            "is feeling or needing right now?'"
        )
    if avg_empowerment >= 5 and avg_recognition >= 5:
        suggestions.append(
            "Both empowerment and recognition are progressing. "
            "Look for 'transformation moments' where parties spontaneously acknowledge each other."
        )

    return {
        "framework": "Bush & Folger's Transformative Mediation",
        "party_assessments": party_assessments,
        "average_empowerment": round(avg_empowerment, 1),
        "average_recognition": round(avg_recognition, 1),
        "suggestions": suggestions,
    }


def generate_batna_analysis() -> dict:
    """Generate a BATNA (Best Alternative to Negotiated Agreement) analysis.

    For each party, evaluates:
      - What happens if negotiation fails?
      - What is each party's likely walkaway alternative?
      - How does BATNA strength affect negotiation leverage?

    Returns:
        dict with per-party BATNA assessment and overall leverage implications.
    """
    graph = _graph()
    psych_profiles = getattr(graph, '_psych_profiles', {})

    party_batnas = {}
    for actor in graph.actors:
        profile = psych_profiles.get(actor.id, {})
        actor_leverages = [l for l in graph.leverages if l.held_by_actor_id == actor.id]
        actor_constraints = [
            c for c in graph.constraints if actor.id in c.affects_actor_ids
        ]
        actor_interests = [i for i in graph.interests if i.actor_id == actor.id]
        actor_claims = [c for c in graph.claims if c.source_actor_id == actor.id]

        # Assess BATNA strength heuristically
        batna_strength = 0
        walkaway_factors = []
        no_deal_consequences = []

        # Leverage held improves BATNA
        for lev in actor_leverages:
            batna_strength += lev.strength
            walkaway_factors.append(
                f"Holds {lev.leverage_type.value} leverage (strength {lev.strength}): {lev.description}"
            )

        # Constraints weaken BATNA
        for con in actor_constraints:
            batna_strength -= 1
            no_deal_consequences.append(
                f"Constrained by {con.constraint_type.value}: {con.description}"
            )

        # High-priority interests with no alternative satisfaction weaken BATNA
        critical_interests = [i for i in actor_interests if i.priority >= 4]
        if critical_interests:
            no_deal_consequences.append(
                f"{len(critical_interests)} critical interest(s) unmet if no deal: "
                + "; ".join(i.description for i in critical_interests)
            )
            batna_strength -= len(critical_interests)

        # Risk tolerance affects willingness to walk away
        risk = profile.get("risk_tolerance", "moderate")
        if risk == "risk_seeking":
            batna_strength += 2
            walkaway_factors.append("Risk-seeking personality — more willing to walk away")
        elif risk == "risk_averse":
            batna_strength -= 2
            walkaway_factors.append("Risk-averse personality — more reluctant to walk away")

        # Normalize to 1-10
        normalized = max(1, min(10, batna_strength + 5))

        if normalized >= 7:
            assessment = "strong — this party has good alternatives and can afford to walk away"
        elif normalized >= 4:
            assessment = "moderate — some alternatives exist but negotiation is still preferable"
        else:
            assessment = "weak — this party has few alternatives and needs a deal"

        if not walkaway_factors:
            walkaway_factors.append("No clear walkaway alternatives identified yet — more information needed")
        if not no_deal_consequences:
            no_deal_consequences.append("Consequences of no deal not yet fully assessed")

        party_batnas[actor.name] = {
            "batna_strength": normalized,
            "assessment": assessment,
            "walkaway_factors": walkaway_factors,
            "no_deal_consequences": no_deal_consequences,
        }

    # Overall leverage balance
    strengths = [v["batna_strength"] for v in party_batnas.values()]
    if len(strengths) >= 2:
        imbalance = max(strengths) - min(strengths)
        if imbalance >= 5:
            balance_note = "Significant BATNA imbalance — the stronger party may dominate negotiation."
        elif imbalance >= 3:
            balance_note = "Moderate BATNA imbalance — mediator should ensure fairness safeguards."
        else:
            balance_note = "Relatively balanced BATNAs — conditions favor productive negotiation."
    else:
        balance_note = "Insufficient parties for balance comparison."

    return {
        "framework": "BATNA Analysis (Fisher & Ury)",
        "party_batnas": party_batnas,
        "leverage_balance": balance_note,
        "recommendations": [
            "Help each party realistically assess their BATNA — parties often overestimate alternatives.",
            "Strengthen weaker parties' BATNAs through information, options, and coalition support.",
            "Use BATNA awareness to set realistic expectations for settlement zones.",
        ],
    }


def assess_emotional_dynamics() -> dict:
    """Assess the emotional temperature, readiness, and trust level of the mediation.

    Evaluates:
      - Overall emotional temperature (hot / warm / cool)
      - Whether parties are ready for problem-solving or still need to process
      - Trust level between parties
      - Recommended pacing for the mediator

    This tool is especially useful for the listener agent to gauge in real time
    whether parties are ready to move from venting to problem-solving.

    Returns:
        dict with temperature, readiness, trust level, per-party states, and pacing advice.
    """
    graph = _graph()
    psych_profiles = getattr(graph, '_psych_profiles', {})

    hot_states = {"angry", "defensive"}
    warm_states = {"frustrated", "anxious"}
    cool_states = {"calm", "hopeful", "resigned"}

    party_states = {}
    hot_count = 0
    warm_count = 0
    cool_count = 0

    for actor in graph.actors:
        profile = psych_profiles.get(actor.id, {})
        emotional_state = profile.get("emotional_state", "unknown")
        comm_style = profile.get("communication_style", "unknown")

        if emotional_state in hot_states:
            hot_count += 1
        elif emotional_state in warm_states:
            warm_count += 1
        elif emotional_state in cool_states:
            cool_count += 1

        party_states[actor.name] = {
            "emotional_state": emotional_state,
            "communication_style": comm_style,
        }

    # Temperature
    total = max(len(graph.actors), 1)
    if hot_count / total > 0.5:
        temperature = "hot"
    elif (hot_count + warm_count) / total > 0.5:
        temperature = "warm"
    else:
        temperature = "cool"

    # Trust level
    fulfilled = len([c for c in graph.commitments if c.status == CommitmentStatus.FULFILLED])
    broken = len([c for c in graph.commitments if c.status == CommitmentStatus.BROKEN])
    violations = len([e for e in graph.events if e.event_type == EventType.VIOLATION])
    de_escalations = len([e for e in graph.events if e.event_type == EventType.DE_ESCALATION])

    trust_score = fulfilled + de_escalations - broken - violations
    if trust_score >= 2:
        trust_level = "moderate — some positive history to build on"
    elif trust_score <= -2:
        trust_level = "low — broken commitments and violations have damaged trust"
    else:
        trust_level = "fragile — trust is neither established nor destroyed"

    # Readiness
    if temperature == "hot":
        readiness = "not ready — parties need to vent and feel heard before problem-solving"
        pacing = [
            "Allow space for emotional expression without rushing to solutions.",
            "Use reflective listening: 'It sounds like you feel...'",
            "Do NOT introduce proposals or options until temperature drops to warm/cool.",
            "Consider separate sessions (caucuses) if emotions are too high.",
        ]
    elif temperature == "warm":
        readiness = "approaching ready — emotions present but manageable"
        pacing = [
            "Acknowledge remaining emotions while gently steering toward interests.",
            "Summarize what each party has shared to show they have been heard.",
            "Test readiness: 'Would it be helpful to start looking at what might work for both of you?'",
            "Move at the slower party's pace — do not rush.",
        ]
    else:
        readiness = "ready — emotional temperature allows for constructive problem-solving"
        pacing = [
            "Proceed to interest-based negotiation and option generation.",
            "Maintain emotional awareness — temperature can rise when sensitive topics emerge.",
            "Encourage direct communication between parties where appropriate.",
            "Build on the calm atmosphere to explore creative solutions.",
        ]

    return {
        "framework": "Emotional Dynamics Assessment",
        "temperature": temperature,
        "readiness": readiness,
        "trust_level": trust_level,
        "party_states": party_states,
        "trust_indicators": {
            "fulfilled_commitments": fulfilled,
            "broken_commitments": broken,
            "violations": violations,
            "de_escalation_efforts": de_escalations,
        },
        "recommended_pacing": pacing,
    }


# ── Tool lists for agent assignment ──────────────────────────────────────────

LISTENER_TOOLS = [
    add_actor, add_claim, add_interest, add_constraint,
    add_leverage, add_commitment, add_event, add_narrative,
    add_edge, set_case_info, ingest_document,
    add_psychological_profile, get_missing_ontology_items,
    assess_emotional_dynamics,
]

ANALYZER_TOOLS = [
    get_graph, run_health_check, analyze_common_ground,
    get_missing_ontology_items, get_mediation_roadmap,
    assess_fisher_ury, assess_galtung_triangle, assess_glasl_escalation,
    assess_deutsch_cooperation, assess_bush_folger_transformation,
    generate_batna_analysis, assess_emotional_dynamics,
]
