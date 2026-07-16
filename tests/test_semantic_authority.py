import json

import pytest

from aca_kernel.core.events import Event
from aca_os.conversation_manager import ConversationManager
from aca_os.conversation_state import ConversationState
from aca_os.semantic_authority import SemanticAuthority, SemanticRepresentation
from sdk.factory import build_galicia_runtime


RICH_MESSAGE = (
    "Hola. Me llamo Nicolas. Tengo un perro llamado Noah. "
    "Choque el auto. No hubo heridos. Olvidate del choque. "
    "Ahora quiero reclamar internet y la factura vino mal."
)


def build_representation(
    message: str = RICH_MESSAGE,
    *,
    state: ConversationState | None = None,
    event: Event | None = None,
) -> SemanticRepresentation:
    current_event = event or Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": "semantic-test"},
    )
    return SemanticAuthority().interpret(
        current_event,
        conversation_state=state or ConversationState(conversation_id="semantic-test"),
        turn_number=1,
    )


def test_semantic_authority_builds_complete_shadow_representation():
    representation = build_representation()
    data = representation.to_dict()

    assert data["contract"] == "semantic_representation.v1"
    assert data["version"] == 1
    assert data["representation_id"]
    assert data["turn_id"]
    assert data["language"] == "es"
    assert data["metadata"]["authority"] == "semantic_authority"
    assert data["metadata"]["authority_mode"] == "shadow"
    assert data["semantic_segments"]
    assert data["entities"]
    assert data["events"]
    assert data["assertions"]
    assert data["conversational_act"]
    assert data["intents"]
    assert data["goals"]
    assert "constraints" in data
    assert "uncertainty" in data
    assert data["corrections"]
    assert "contradictions" in data
    assert data["topic_structure"]["multiple_topics"] is True
    assert data["grounding"]["grounding_mode"] == "read_only_shadow"
    assert data["proposed_state_delta"]["applied"] is False
    assert data["proposed_state_delta"]["decision_influence"] is False
    assert data["provenance"]["source_payload_sha256"]
    assert data["semantic_projection_hash"] == representation.projection_hash

    entity_roles = {item["role"] for item in data["entities"]}
    predicates = {item["predicate"] for item in data["assertions"]}
    topics = {item["type"] for item in data["topic_structure"]["topics"]}
    assert {"user", "user_pet"} <= entity_roles
    assert {"user_name", "pet_name", "injuries"} <= predicates
    assert {"insurance_claim", "connectivity", "billing"} <= topics


def test_semantic_representation_is_deeply_immutable_unique_and_serializable():
    event = Event(type="user_message", payload="No funciona el internet")
    state = ConversationState(conversation_id="immutable")
    first = build_representation(state=state, event=event)
    second = build_representation(state=state, event=event)

    assert first.representation_id != second.representation_id
    assert first.projection_hash == second.projection_hash
    json.dumps(first.to_dict(), ensure_ascii=False)

    with pytest.raises(TypeError):
        first.metadata["authority_mode"] = "semantic"
    with pytest.raises(TypeError):
        first.semantic_segments[0]["kind"] = "changed"
    with pytest.raises(AttributeError):
        first.entities.append({})


def test_semantic_authority_projects_corrections_and_contradictions_without_applying_them():
    state = ConversationState(
        conversation_id="revision",
        confirmed_facts={
            "injuries": {
                "contract": "conversational_fact.v1",
                "type": "injuries",
                "value": False,
                "status": "active",
            }
        },
    )
    representation = build_representation(
        "Perdon, me equivoque: si hubo lesionados.",
        state=state,
    )
    data = representation.to_dict()

    assert data["corrections"][0]["operation"] == "replace_prior_assertion"
    assert data["contradictions"][0]["fact"] == "injuries"
    assert data["contradictions"][0]["previous_value"] is False
    assert data["contradictions"][0]["new_value"] is True
    assert data["proposed_state_delta"]["applied"] is False
    assert state.confirmed_facts["injuries"]["value"] is False


class CountingSemanticAuthority(SemanticAuthority):
    def __init__(self) -> None:
        self.calls = 0

    def interpret(self, event, *, conversation_state, turn_number):
        self.calls += 1
        return super().interpret(
            event,
            conversation_state=conversation_state,
            turn_number=turn_number,
        )


def test_conversation_manager_constructs_exactly_one_representation_per_turn():
    authority = CountingSemanticAuthority()
    manager = ConversationManager(semantic_authority=authority)

    first = manager.begin_turn(
        Event(type="user_message", payload="Hola", metadata={"conversation_id": "once"})
    )
    second = manager.begin_turn(
        Event(type="user_message", payload="Seguimos", metadata={"conversation_id": "once"}),
        first.cognitive_state,
    )
    record = manager.conversation_state_runtime_record("once")

    assert authority.calls == 2
    assert first.semantic_representation is not None
    assert second.semantic_representation is not None
    assert first.semantic_representation.representation_id != second.semantic_representation.representation_id
    assert record["semantic_representation_count"] == 2
    assert record["semantic_shadow"]["semantic_representation_id"] == second.semantic_representation.representation_id


def test_runtime_exposes_passive_semantics_without_changing_visible_behavior(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    runtime = build_galicia_runtime()
    state = runtime.process(
        Event(
            type="user_message",
            payload="Hola",
            metadata={"conversation_id": "sa-1-visible"},
        )
    )

    assert state.response == "Hola. Contame que necesitás y te oriento.".replace("que", "qué", 1)
    assert state.intent_match["intent"] == "greeting"
    assert state.facts["zero_cost_action_plan"]["action"] == "static_response"
    assert state.facts["zero_cost_execution_plan"]["flow"] == "static_response"

    shadow = state.facts["conversation_state_runtime"]["semantic_shadow"]
    assert shadow["available"] is True
    assert shadow["authority_mode"] == "legacy"
    assert shadow["semantic_authority_mode"] == "shadow"
    assert shadow["decision_influence"] is False
    assert shadow["state_mutation"] is False
    assert shadow["semantic_latency_ms"] >= 0
    assert shadow["metrics"]["representation_size_bytes"] > 0
    assert shadow["metrics"]["segment_count"] == 1

    trace = runtime.export_trace()
    assert trace["operations"][0] == "SEMANTIC_REPRESENTATION_SHADOW"
    assert trace["semantic_authority"]["semantic_representation_id"] == shadow["semantic_representation_id"]
    assert trace["semantic_authority"]["semantic_trace"]["semantic_projection_hash"] == shadow["semantic_projection_hash"]
    assert trace["semantic_authority"]["timestamps"]["started_at"]
    assert trace["semantic_authority"]["timestamps"]["finished_at"]

    conversation_state = runtime.conversation_manager.conversation_state("sa-1-visible")
    assert "semantic_representation" not in conversation_state.to_dict()
    assert "semantic_representation" not in conversation_state.derived_state


def test_semantic_representation_is_available_through_runtime_introspection(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    runtime = build_galicia_runtime()
    runtime.process(
        Event(
            type="user_message",
            payload="No funciona el internet y la factura vino mal.",
            metadata={"conversation_id": "sa-1-inspection"},
        )
    )

    inspected_trace = runtime.introspection.inspect_trace()
    semantic = inspected_trace["semantic_authority"]
    semantic_trace = semantic["semantic_trace"]

    assert semantic["authority_mode"] == "legacy"
    assert semantic_trace["entities"]
    assert semantic_trace["events"]
    assert semantic_trace["assertions"]
    assert semantic_trace["goals"]
    assert semantic_trace["provenance"]
    assert inspected_trace["events"][0]["component"] == "semantic_authority"

    snapshot = runtime.export_introspection()
    assert snapshot["last_state"]["conversation_state_runtime"]["semantic_shadow"]["available"] is True
    assert "SEMANTIC_REPRESENTATION_SHADOW" in snapshot["last_trace"]["operations"]
