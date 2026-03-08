"""Tests for multi-party mediation flow."""

import pytest
import asyncio
from mediation import CaseManager, MediationPhase, PartyStatus


@pytest.fixture
def manager():
    return CaseManager()


@pytest.mark.asyncio
async def test_create_case(manager):
    case = await manager.create_case(["Alice", "Bob"])
    assert case.case_id
    assert len(case.parties) == 2
    assert case.phase == MediationPhase.INTAKE_PARTY_1


@pytest.mark.asyncio
async def test_party_states(manager):
    case = await manager.create_case(["Alice", "Bob"])
    pids = list(case.parties.keys())
    assert case.parties[pids[0]].status == PartyStatus.ACTIVE
    assert case.parties[pids[1]].status == PartyStatus.WAITING


@pytest.mark.asyncio
async def test_phase_advancement(manager):
    case = await manager.create_case(["Alice", "Bob"])
    assert case.phase == MediationPhase.INTAKE_PARTY_1
    case.advance_phase()
    assert case.phase == MediationPhase.INTAKE_PARTY_2
    case.advance_phase()
    assert case.phase == MediationPhase.JOINT_SESSION
    case.advance_phase()
    assert case.phase == MediationPhase.RESOLUTION


@pytest.mark.asyncio
async def test_graph_isolation(manager):
    case1 = await manager.create_case(["A", "B"])
    case2 = await manager.create_case(["C", "D"])
    assert case1.graph is not case2.graph
    from concordia_agent.ontology import Actor, ActorType
    case1.graph.actors.append(Actor(name="X", actor_type=ActorType.INDIVIDUAL))
    assert len(case1.graph.actors) == 1
    assert len(case2.graph.actors) == 0


@pytest.mark.asyncio
async def test_per_party_tracking(manager):
    case = await manager.create_case(["Alice", "Bob"])
    from concordia_agent.ontology import Actor, ActorType
    pid = list(case.parties.keys())[0]
    case.graph.actors.append(
        Actor(name="Alice Actor", actor_type=ActorType.INDIVIDUAL, contributed_by=pid))
    h = case.graph.per_party_health_check(pid)
    assert h["counts"]["actors"] == 1


@pytest.mark.asyncio
async def test_case_summary(manager):
    case = await manager.create_case(["Alice", "Bob"], title="Test")
    s = case.summary()
    assert s["case_id"] == case.case_id
    assert s["title"] == "Test"
    assert "parties" in s


@pytest.mark.asyncio
async def test_list_cases(manager):
    await manager.create_case(["A", "B"])
    await manager.create_case(["C", "D"])
    cases = await manager.list_cases()
    assert len(cases) == 2


@pytest.mark.asyncio
async def test_too_few_parties(manager):
    with pytest.raises(ValueError):
        await manager.create_case(["Only One"])
