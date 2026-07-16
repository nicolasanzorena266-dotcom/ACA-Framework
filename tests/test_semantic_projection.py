import json
from copy import deepcopy

import pytest

from aca_kernel.core.events import Event
from aca_os.conversation_manager import ConversationManager
from aca_os.conversation_state import ConversationState
from aca_os.semantic_authority import SemanticAuthority
from aca_os.semantic_projection import (
    PROJECTION_NAMES,
    SemanticProjection,
    SemanticProjector,
    compare_semantic_projection,
)
from sdk.factory import build_galicia_runtime


def build_projection(
    message: str,
    *,
    state: ConversationState | None = None,
) -> SemanticProjection:
    event = Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": "semantic-projection-test"},
    )
    representation = SemanticAuthority().interpret(
        event,
        conversation_state=state or ConversationState(conversation_id="semantic-projection-test"),
        turn_number=1,
    )
    return SemanticProjector().project(representation)


def test_semantic_projector_builds_all_required_contracts_from_representation():
    projection = build_projection(
        "Me llamo Nicolas. Choque el auto. No hubo heridos. "
        "Ahora quiero reclamar internet."
    )
    data = projection.to_dict()

    assert data["contract"] == "semantic_projection.v1"
    assert data["version"] == 1
    assert data["projection_id"]
    assert data["representation_id"]
    assert data["projection_hash"] == projection.projection_hash
    assert all(name in data for name in PROJECTION_NAMES)
    assert data["conversational_act"]["contract"] == "conversational_act.v1"
    assert data["conversation_intent_model"]["contract"] == "conversational_intent_model.v1"
    assert data["intent_projection"]["contract"] == "intent_projection.v1"
    assert data["entity_projection"]["contract"] == "entity_projection.v1"
    assert data["fact_projection"]["contract"] == "fact_projection.v1"
    assert data["slot_projection"]["contract"] == "slot_projection.v1"
    assert data["topic_projection"]["contract"] == "topic_projection.v1"
    assert data["goal_projection"]["contract"] == "goal_projection.v1"
    assert data["metadata"]["mode"] == "shadow"
    assert data["metadata"]["decision_influence"] is False
    assert data["metadata"]["state_mutation"] is False


def test_semantic_projection_is_deeply_immutable_serializable_and_hash_stable():
    first = build_projection("Me llamo Nicolas y no hubo heridos.")
    second = build_projection("Me llamo Nicolas y no hubo heridos.")

    assert first.projection_id != second.projection_id
    assert first.representation_id != second.representation_id
    assert first.projection_hash == second.projection_hash
    json.dumps(first.to_dict(), ensure_ascii=False)

    with pytest.raises(TypeError):
        first.metadata["mode"] = "official"
    with pytest.raises(TypeError):
        first.fact_projection["items"][0]["value"] = True
    with pytest.raises(AttributeError):
        first.topic_projection["topics"].append({})


def test_projection_comparison_reports_match_difference_and_metrics():
    projection = build_projection("Me llamo Nicolas. No hubo heridos.")
    identical_legacy = projection.to_dict()
    matching = compare_semantic_projection(identical_legacy, projection)

    assert matching["overall_status"] == "MATCH"
    assert matching["status_counts"]["MATCH"] == len(PROJECTION_NAMES)
    assert all(item["status"] == "MATCH" for item in matching["projection_diff"].values())
    assert all(value == 1.0 for value in matching["metrics"].values())
    assert matching["projection_hash"]
    json.dumps(matching, ensure_ascii=False)

    changed_legacy = deepcopy(identical_legacy)
    changed_legacy["fact_projection"]["items"][0]["value"] = "different"
    changed_legacy["intent_projection"]["selected"]["intent"] = "legacy_other"
    changed = compare_semantic_projection(changed_legacy, projection)

    assert changed["overall_status"] == "DIFFERENT"
    assert changed["projection_diff"]["fact_projection"]["status"] == "DIFFERENT"
    assert changed["projection_diff"]["intent_projection"]["status"] == "DIFFERENT"
    assert changed["metrics"]["fact_recall"] < 1.0
    assert changed["metrics"]["intent_agreement"] == 0.0
    assert changed["field_diff"]


def test_semantic_projection_models_required_special_cases():
    negation = build_projection("No hubo heridos.").to_dict()
    assert negation["fact_projection"]["items"][0]["type"] == "injuries"
    assert negation["fact_projection"]["items"][0]["value"] is False

    correction = build_projection("Perdon. Me equivoque.").to_dict()
    assert correction["conversational_act"]["act"] == "correction"
    assert correction["fact_projection"]["corrections"]

    retraction = build_projection("Olvidate de eso.").to_dict()
    assert retraction["fact_projection"]["corrections"][0]["operation"] == "retract"

    topic_shift = build_projection("Ahora quiero hablar de internet.").to_dict()
    assert topic_shift["conversational_act"]["act"] == "topic_shift"
    assert topic_shift["topic_projection"]["active_topic"]["type"] == "connectivity"

    immediate_memory = build_projection("Me llamo Nicolas.").to_dict()
    assert any(item["role"] == "user" for item in immediate_memory["entity_projection"]["items"])
    assert any(item["type"] == "user_name" for item in immediate_memory["fact_projection"]["items"])
    assert any(item["name"] == "user_name" for item in immediate_memory["slot_projection"]["items"])

    multiple_topics = build_projection("Choque. Ademas quiero reclamar internet.").to_dict()
    assert multiple_topics["topic_projection"]["multiple_topics"] is True
    assert {item["type"] for item in multiple_topics["topic_projection"]["topics"]} == {
        "insurance_claim",
        "connectivity",
    }


class CountingSemanticProjector(SemanticProjector):
    def __init__(self) -> None:
        self.calls = 0

    def project(self, representation):
        self.calls += 1
        return super().project(representation)


def test_conversation_manager_builds_exactly_one_semantic_projection_per_turn():
    projector = CountingSemanticProjector()
    manager = ConversationManager(semantic_projector=projector)

    first = manager.begin_turn(
        Event(type="user_message", payload="Hola", metadata={"conversation_id": "sa2-once"})
    )
    second = manager.begin_turn(
        Event(type="user_message", payload="Seguimos", metadata={"conversation_id": "sa2-once"}),
        first.cognitive_state,
    )
    record = manager.conversation_state_runtime_record("sa2-once")

    assert projector.calls == 2
    assert first.semantic_projection is not None
    assert second.semantic_projection is not None
    assert first.semantic_projection.projection_id != second.semantic_projection.projection_id
    assert record["semantic_projection_count"] == 2
    assert record["semantic_projection_shadow"]["semantic_projection_id"] == second.semantic_projection.projection_id


def test_runtime_exposes_projection_diff_without_changing_visible_behavior(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    runtime = build_galicia_runtime()
    state = runtime.process(
        Event(
            type="user_message",
            payload="Hola",
            metadata={"conversation_id": "sa2-visible"},
        )
    )

    assert state.response == "Hola. Contame qué necesitás y te oriento."
    assert state.intent_match["intent"] == "greeting"
    assert state.facts["zero_cost_action_plan"]["action"] == "static_response"
    assert state.facts["zero_cost_execution_plan"]["flow"] == "static_response"

    shadow = state.facts["conversation_state_runtime"]["semantic_projection_shadow"]
    assert shadow["available"] is True
    assert shadow["authority_mode"] == "legacy"
    assert shadow["semantic_authority_mode"] == "shadow"
    assert shadow["decision_influence"] is False
    assert shadow["state_mutation"] is False
    assert set(shadow["projection_diff"]) == set(PROJECTION_NAMES)
    assert set(shadow["metrics"]) == {
        "entity_recall",
        "entity_precision",
        "fact_recall",
        "fact_precision",
        "slot_recall",
        "slot_precision",
        "topic_agreement",
        "intent_agreement",
        "goal_agreement",
    }

    trace = runtime.export_trace()
    assert trace["operations"][:2] == [
        "SEMANTIC_REPRESENTATION_SHADOW",
        "SEMANTIC_PROJECTION_SHADOW",
    ]
    assert trace["semantic_projection"]["semantic_projection"]
    assert trace["semantic_projection"]["legacy_projection"]
    assert trace["semantic_projection"]["projection_diff"]

    inspected = runtime.introspection.inspect_trace()
    assert inspected["semantic_projection"]["field_diff"] == shadow["field_diff"]
    assert inspected["semantic_projection"]["semantic_projection_hash"] == shadow["semantic_projection_hash"]

    conversation_state = runtime.conversation_manager.conversation_state("sa2-visible")
    assert "semantic_projection" not in conversation_state.to_dict()
    assert "semantic_projection" not in conversation_state.derived_state
