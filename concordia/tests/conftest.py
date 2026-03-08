"""
CONCORDIA Test Fixtures
"""

import sys
from pathlib import Path

# Add app/ to sys.path so imports work like they do at runtime
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pytest
import concordia_agent.ontology as ontology
from concordia_agent.ontology import (
    ConflictGraph, Actor, ActorType, Claim, ClaimType,
    Interest, InterestType, Constraint, ConstraintType,
    Leverage, LeverageType, Commitment, CommitmentStatus,
    Event, EventType, Narrative, Edge, EscalationLevel, Phase,
)


@pytest.fixture
def empty_graph():
    """Fresh empty ConflictGraph."""
    return ConflictGraph()


@pytest.fixture
def populated_graph():
    """Graph with 2 actors and full conflict data (HR dispute)."""
    g = ConflictGraph(
        case_title="Workplace Performance Dispute",
        case_summary="Alex and Maya disagree about code review process.",
    )
    alex = Actor(name="Alex", actor_type=ActorType.INDIVIDUAL,
                 description="Senior developer, 5 years tenure",
                 role_in_conflict="complainant", contributed_by="party_a")
    maya = Actor(name="Maya", actor_type=ActorType.INDIVIDUAL,
                 description="Team lead, responsible for sprint delivery",
                 role_in_conflict="respondent", contributed_by="party_b")
    g.actors.extend([alex, maya])

    c1 = Claim(claim_type=ClaimType.GRIEVANCE, content="Maya publicly criticized my code reviews",
               source_actor_id=alex.id, target_actor_id=maya.id, contributed_by="party_a")
    c2 = Claim(claim_type=ClaimType.DEMAND, content="Want formal apology and clear review guidelines",
               source_actor_id=alex.id, contributed_by="party_a")
    c3 = Claim(claim_type=ClaimType.PROPOSAL, content="24-hour review SLA for minor changes",
               source_actor_id=maya.id, target_actor_id=alex.id, contributed_by="party_b")
    g.claims.extend([c1, c2, c3])

    i1 = Interest(interest_type=InterestType.RECOGNITION, description="Professional respect",
                  actor_id=alex.id, priority=5, contributed_by="party_a")
    i2 = Interest(interest_type=InterestType.PROCEDURAL, description="Clear process for reviews",
                  actor_id=alex.id, priority=4, contributed_by="party_a")
    i3 = Interest(interest_type=InterestType.PROCEDURAL, description="Efficient sprint delivery",
                  actor_id=maya.id, priority=5, contributed_by="party_b")
    i4 = Interest(interest_type=InterestType.RECOGNITION, description="Authority as team lead",
                  actor_id=maya.id, priority=4, contributed_by="party_b")
    g.interests.extend([i1, i2, i3, i4])

    con = Constraint(constraint_type=ConstraintType.TEMPORAL,
                     description="Sprint deadlines every 2 weeks",
                     affects_actor_ids=[alex.id, maya.id], contributed_by="party_b")
    g.constraints.append(con)

    lev = Leverage(leverage_type=LeverageType.STRUCTURAL,
                   description="Maya has authority over task assignments",
                   held_by_actor_id=maya.id, target_actor_id=alex.id,
                   strength=4, contributed_by="party_b")
    g.leverages.append(lev)

    com = Commitment(description="Team agreed to follow code review checklist",
                     committed_actor_id=alex.id, to_actor_id=maya.id,
                     status=CommitmentStatus.BROKEN, contributed_by="party_b")
    g.commitments.append(com)

    ev = Event(event_type=EventType.ESCALATION,
               description="Maya criticized Alex's reviews in team meeting",
               date="last Monday", involved_actor_ids=[alex.id, maya.id],
               contributed_by="party_a")
    g.events.append(ev)

    n1 = Narrative(description="Alex frames himself as the quality guardian being silenced",
                   held_by_actor_id=alex.id, frames=["victim", "justice"],
                   contributed_by="party_a")
    n2 = Narrative(description="Maya frames the issue as a process bottleneck",
                   held_by_actor_id=maya.id, frames=["efficiency", "leadership"],
                   contributed_by="party_b")
    g.narratives.extend([n1, n2])

    # Add edges
    g.edges.append(Edge(source_id=alex.id, target_id=c1.id, relationship="MAKES_CLAIM"))
    g.edges.append(Edge(source_id=maya.id, target_id=c3.id, relationship="MAKES_CLAIM"))
    g.edges.append(Edge(source_id=alex.id, target_id=i1.id, relationship="HAS_INTEREST"))
    g.edges.append(Edge(source_id=maya.id, target_id=i3.id, relationship="HAS_INTEREST"))

    return g


@pytest.fixture(autouse=True)
def reset_graph_state():
    """Reset the module-level graph state before each test."""
    ontology.graph = ConflictGraph()
    ontology.active_party = "default"
    yield
    ontology.graph = ConflictGraph()
    ontology.active_party = "default"
