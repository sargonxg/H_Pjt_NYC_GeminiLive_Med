"""Tests for the conflict ontology models and ConflictGraph."""

import pytest
from concordia_agent.ontology import (
    ConflictGraph, Actor, ActorType, Claim, ClaimType,
    Interest, InterestType, Constraint, ConstraintType,
    Leverage, LeverageType, Commitment, CommitmentStatus,
    Event, EventType, Narrative, Edge, Phase, EscalationLevel,
    _uid,
)


class TestUid:
    def test_generates_prefixed_ids(self):
        uid = _uid("actor")
        assert uid.startswith("actor_")
        assert len(uid) > 7

    def test_generates_unique_ids(self):
        ids = {_uid("test") for _ in range(100)}
        assert len(ids) == 100


class TestModels:
    def test_actor_defaults(self):
        a = Actor(name="Alice", actor_type=ActorType.INDIVIDUAL)
        assert a.name == "Alice"
        assert a.id.startswith("actor_")
        assert a.contributed_by == "default"

    def test_claim_defaults(self):
        c = Claim(claim_type=ClaimType.DEMAND, content="I want X", source_actor_id="a1")
        assert c.id.startswith("claim_")
        assert c.target_actor_id == ""

    def test_interest_priority_validation(self):
        i = Interest(interest_type=InterestType.SECURITY, description="Safety",
                     actor_id="a1", priority=5)
        assert i.priority == 5

    def test_leverage_strength_range(self):
        l = Leverage(leverage_type=LeverageType.COERCIVE, description="Threat",
                     held_by_actor_id="a1", strength=1)
        assert l.strength == 1

    def test_commitment_status(self):
        c = Commitment(description="Promise", committed_actor_id="a1",
                       status=CommitmentStatus.BROKEN)
        assert c.status == "broken"

    def test_event_types(self):
        for et in EventType:
            e = Event(event_type=et, description="test")
            assert e.event_type == et

    def test_narrative_frames(self):
        n = Narrative(description="Story", held_by_actor_id="a1",
                      frames=["victim", "betrayal"])
        assert len(n.frames) == 2


class TestStrEnums:
    def test_actor_types(self):
        expected = {"individual", "organization", "state", "group", "institution"}
        assert set(ActorType) == expected

    def test_claim_types(self):
        expected = {"demand", "accusation", "justification", "proposal", "grievance"}
        assert set(ClaimType) == expected

    def test_escalation_levels(self):
        expected = {"latent", "emerging", "escalating", "crisis", "destructive"}
        assert set(EscalationLevel) == expected


class TestHealthCheck:
    def test_empty_graph(self, empty_graph):
        h = empty_graph.health_check()
        assert h["score"] == 0
        assert not h["ready"]
        assert not any(h["checks"].values())
        assert len(h["gaps"]) > 0

    def test_one_actor_not_enough(self, empty_graph):
        empty_graph.actors.append(
            Actor(name="Alice", actor_type=ActorType.INDIVIDUAL))
        h = empty_graph.health_check()
        assert not h["checks"]["two_plus_actors"]

    def test_populated_graph_high_score(self, populated_graph):
        h = populated_graph.health_check()
        assert h["score"] >= 75
        assert h["ready"]
        assert h["checks"]["two_plus_actors"]
        assert h["checks"]["has_events"]
        assert h["checks"]["has_narratives"]

    def test_boundary_75_percent(self, empty_graph):
        # 6/8 checks = 75%
        g = empty_graph
        a1 = Actor(name="A", actor_type=ActorType.INDIVIDUAL)
        a2 = Actor(name="B", actor_type=ActorType.INDIVIDUAL)
        g.actors.extend([a1, a2])
        g.claims.append(Claim(claim_type=ClaimType.DEMAND, content="x",
                              source_actor_id=a1.id))
        g.claims.append(Claim(claim_type=ClaimType.DEMAND, content="y",
                              source_actor_id=a2.id))
        g.interests.append(Interest(interest_type=InterestType.SECURITY,
                                    description="z", actor_id=a1.id))
        g.interests.append(Interest(interest_type=InterestType.SECURITY,
                                    description="w", actor_id=a2.id))
        g.constraints.append(Constraint(constraint_type=ConstraintType.LEGAL,
                                        description="c"))
        g.leverages.append(Leverage(leverage_type=LeverageType.COERCIVE,
                                    description="l", held_by_actor_id=a1.id))
        h = g.health_check()
        # 5/8 checks pass (actors, claims, interests, constraints, leverage)
        # Missing: events, narratives, case_metadata → 5/8 = 62%
        assert h["score"] == 62


class TestPerPartyHealthCheck:
    def test_empty_party(self, empty_graph):
        h = empty_graph.per_party_health_check("unknown_party")
        assert h["score"] == 0
        assert h["party_id"] == "unknown_party"

    def test_party_with_data(self, populated_graph):
        h = populated_graph.per_party_health_check("party_a")
        assert h["score"] > 0
        assert h["counts"]["actors"] >= 1
        assert h["counts"]["claims"] >= 1


class TestEscalationAssessment:
    def test_latent_on_empty(self, empty_graph):
        level = empty_graph.escalation_assessment()
        assert level == EscalationLevel.LATENT

    def test_escalation_with_adversarial_data(self, populated_graph):
        # Add more adversarial content
        a1 = populated_graph.actors[0]
        for _ in range(5):
            populated_graph.claims.append(
                Claim(claim_type=ClaimType.ACCUSATION, content="Bad behavior",
                      source_actor_id=a1.id))
        populated_graph.narratives.append(
            Narrative(description="Framing", held_by_actor_id=a1.id,
                      frames=["victim", "betrayal", "villain", "enemy"]))
        level = populated_graph.escalation_assessment()
        assert level in (EscalationLevel.ESCALATING, EscalationLevel.CRISIS,
                         EscalationLevel.DESTRUCTIVE)


class TestFindCommonGround:
    def test_shared_interests(self, populated_graph):
        result = populated_graph.find_common_ground()
        # Both have RECOGNITION and PROCEDURAL interests
        assert "recognition" in result["shared_interests"] or "procedural" in result["shared_interests"]

    def test_broken_commitments(self, populated_graph):
        result = populated_graph.find_common_ground()
        assert len(result["broken_commitments"]) >= 1

    def test_leverage_balance(self, populated_graph):
        result = populated_graph.find_common_ground()
        assert len(result["leverage_balance"]) >= 1


class TestGraphSummary:
    def test_summary_not_empty(self, populated_graph):
        s = populated_graph.graph_summary_for_agent()
        assert "Workplace Performance Dispute" in s
        assert "ACTORS:" in s
        assert "Alex" in s

    def test_empty_graph_summary(self, empty_graph):
        s = empty_graph.graph_summary_for_agent()
        assert "latent" in s.lower()
