"""Tests for the tool functions."""

import pytest
import concordia_agent.ontology as ontology
from concordia_agent.tools import (
    add_actor, add_claim, add_interest, add_constraint,
    add_leverage, add_commitment, add_event, add_narrative,
    add_edge, set_case_info, ingest_document,
    get_graph, run_health_check, analyze_common_ground,
    add_psychological_profile, get_missing_ontology_items,
    get_mediation_roadmap,
)


class TestAddActor:
    def test_creates_actor(self):
        r = add_actor("Alice", "individual", "A person", "complainant")
        assert r["status"] == "created"
        assert r["name"] == "Alice"
        assert len(ontology.graph.actors) == 1

    def test_deduplication(self):
        add_actor("Alice", "individual", "A person", "complainant")
        r = add_actor("alice", "individual", "Same person", "complainant")
        assert r["status"] == "already_exists"
        assert len(ontology.graph.actors) == 1

    def test_contributed_by(self):
        ontology.active_party = "party_x"
        add_actor("Bob", "individual", "B", "respondent")
        assert ontology.graph.actors[0].contributed_by == "party_x"


class TestAddClaim:
    def test_creates_claim_with_edges(self):
        add_actor("Alice", "individual", "A", "c")
        add_actor("Bob", "individual", "B", "r")
        a_id = ontology.graph.actors[0].id
        b_id = ontology.graph.actors[1].id
        r = add_claim("demand", "I want X", a_id, b_id)
        assert r["id"].startswith("claim_")
        assert "MAKES_CLAIM" in r["edges"]
        assert "CLAIM_TARGETS" in r["edges"]
        assert len(ontology.graph.edges) >= 2

    def test_claim_without_target(self):
        add_actor("Alice", "individual", "A", "c")
        a_id = ontology.graph.actors[0].id
        r = add_claim("grievance", "Life is unfair", a_id, "")
        assert "CLAIM_TARGETS" not in r["edges"]


class TestAddInterest:
    def test_creates_interest(self):
        add_actor("Alice", "individual", "A", "c")
        a_id = ontology.graph.actors[0].id
        r = add_interest("security", "Physical safety", a_id, 5)
        assert r["id"].startswith("interest_")
        assert len(ontology.graph.interests) == 1
        assert ontology.graph.interests[0].priority == 5


class TestAddConstraint:
    def test_creates_with_multiple_actors(self):
        add_actor("A", "individual", "", "")
        add_actor("B", "individual", "", "")
        ids = ",".join(a.id for a in ontology.graph.actors)
        r = add_constraint("legal", "Contract clause", ids)
        assert r["edges_created"] == 2


class TestAddLeverage:
    def test_creates_leverage_with_edges(self):
        add_actor("A", "individual", "", "")
        add_actor("B", "individual", "", "")
        a, b = ontology.graph.actors[0].id, ontology.graph.actors[1].id
        r = add_leverage("coercive", "Can fire", a, b, 4)
        assert r["id"].startswith("leverage_")
        edges = [e.relationship for e in ontology.graph.edges]
        assert "HOLDS_LEVERAGE" in edges
        assert "LEVERAGE_OVER" in edges


class TestAddCommitment:
    def test_creates_commitment(self):
        add_actor("A", "individual", "", "")
        add_actor("B", "individual", "", "")
        a, b = ontology.graph.actors[0].id, ontology.graph.actors[1].id
        r = add_commitment("Will pay rent", a, b, "active")
        assert r["id"].startswith("commitment_")
        assert ontology.graph.commitments[0].status == "active"


class TestAddEvent:
    def test_creates_event(self):
        add_actor("A", "individual", "", "")
        a = ontology.graph.actors[0].id
        r = add_event("trigger", "Argument happened", "last week", a)
        assert r["id"].startswith("event_")
        assert len(ontology.graph.events) == 1


class TestAddNarrative:
    def test_creates_narrative_with_frames(self):
        add_actor("A", "individual", "", "")
        a = ontology.graph.actors[0].id
        r = add_narrative("They see themselves as victim", a, "victim, betrayal")
        assert r["id"].startswith("narrative_")
        assert ontology.graph.narratives[0].frames == ["victim", "betrayal"]


class TestAddEdge:
    def test_creates_custom_edge(self):
        r = add_edge("node_a", "node_b", "ALLIES_WITH", "They are friends")
        assert r["status"] == "created"
        assert len(ontology.graph.edges) == 1


class TestSetCaseInfo:
    def test_sets_case_metadata(self):
        r = set_case_info("Test Case", "A dispute about X", "emerging")
        assert r["status"] == "set"
        assert ontology.graph.case_title == "Test Case"
        assert ontology.graph.escalation_level == "emerging"


class TestIngestDocument:
    def test_ingests_and_returns_content(self):
        r = ingest_document("Contract text here...", "Lease Agreement")
        assert r["status"] == "ingested"
        assert r["name"] == "Lease Agreement"
        assert r["length"] == len("Contract text here...")
        assert len(ontology.graph.documents) == 1


class TestAnalysisTools:
    def test_get_graph(self):
        add_actor("A", "individual", "", "")
        r = get_graph()
        assert "actors" in r
        assert "health" in r
        assert len(r["actors"]) == 1

    def test_run_health_check_sets_phase(self):
        r = run_health_check()
        assert ontology.graph.phase == "verify"
        assert "score" in r

    def test_analyze_common_ground_sets_phase(self):
        r = analyze_common_ground()
        assert ontology.graph.phase == "resolve"
        assert "shared_interests" in r


class TestPsychologicalProfile:
    def test_creates_profile(self):
        add_actor("Alice", "individual", "A person", "complainant")
        a_id = ontology.graph.actors[0].id
        r = add_psychological_profile(
            actor_id=a_id,
            primary_driver="money",
            secondary_driver="fairness",
            communication_style="analytical",
            risk_tolerance="moderate",
            emotional_state="frustrated",
            notes="Focused on financial recovery",
        )
        assert r["status"] == "recorded"
        assert r["primary_driver"] == "money"
        assert hasattr(ontology.graph, '_psych_profiles')
        assert a_id in ontology.graph._psych_profiles


class TestGetMissingOntologyItems:
    def test_empty_graph_has_gaps(self):
        r = get_missing_ontology_items()
        assert r["total_gaps"] > 0
        assert not r["ready"]

    def test_populated_graph_suggests_questions(self):
        add_actor("Alice", "individual", "A", "c")
        add_actor("Bob", "individual", "B", "r")
        r = get_missing_ontology_items()
        assert len(r["suggested_questions"]) > 0
        assert len(r["actors_needing_claims"]) == 2

    def test_filled_graph_has_fewer_gaps(self, populated_graph):
        ontology.graph = populated_graph
        r = get_missing_ontology_items()
        # Populated graph has most things filled
        assert r["actors_needing_claims"] == []
        assert r["actors_needing_interests"] == []


class TestGetMediationRoadmap:
    def test_empty_graph_roadmap(self):
        r = get_mediation_roadmap()
        assert "health_score" in r
        assert "resolution_approaches" in r
        assert len(r["resolution_approaches"]) >= 1  # At least structured dialogue

    def test_populated_graph_roadmap(self, populated_graph):
        ontology.graph = populated_graph
        r = get_mediation_roadmap()
        assert r["health_score"] > 0
        assert len(r["resolution_approaches"]) >= 2
        assert len(r["party_recommendations"]) >= 2
        # Should have red flags for broken commitment
        assert len(r["red_flags"]) >= 1


class TestToolInvalidInputs:
    def test_invalid_actor_type(self):
        with pytest.raises(ValueError):
            add_actor("A", "invalid_type", "", "")

    def test_invalid_claim_type(self):
        with pytest.raises(ValueError):
            add_claim("invalid", "content", "a1", "a2")

    def test_invalid_escalation_level(self):
        with pytest.raises(ValueError):
            set_case_info("T", "S", "nonexistent_level")
