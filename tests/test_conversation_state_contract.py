from dataclasses import fields

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.context_manager import ContextBundle
from aca_os.conversation_state import (
    CONVERSATION_STATE_FIELD_OWNERSHIP,
    ConversationState,
    VALID_CONVERSATION_STATE_CATEGORIES,
    ownership_snapshot,
    validate_ownership,
)
from aca_os.mission_manager import MissionManager
from aca_os.public_conversation_contracts import InteractionSignals, PlannerDecision, SemanticParse, SupervisorResult
from aca_os.public_conversation_state import PublicConversationState
from sdk.factory import build_galicia_runtime


def test_conversation_state_ownership_covers_every_contract_field_once():
    contract_fields = {field.name for field in fields(ConversationState)}

    assert set(CONVERSATION_STATE_FIELD_OWNERSHIP) == contract_fields
    assert validate_ownership()["valid"] is True
    assert all(ownership.category in VALID_CONVERSATION_STATE_CATEGORIES for ownership in CONVERSATION_STATE_FIELD_OWNERSHIP.values())
    assert all(ownership.owner for ownership in CONVERSATION_STATE_FIELD_OWNERSHIP.values())
    assert all(ownership.writers for ownership in CONVERSATION_STATE_FIELD_OWNERSHIP.values())
    assert ownership_snapshot()["focus"]["owner"] == "conversation_state"


def test_conversation_state_projects_from_cognitive_state_without_runtime_projection_duplication():
    state = CognitiveState(
        conversation_id="contract-runtime",
        facts={
            "event_type": "vehicle_collision",
            "zero_cost_execution_plan": {"flow": "guided_process"},
            "runtime_execution_engine": {"official_engine": "runtime_executor"},
        },
        entities={"event": "vehicle_collision"},
        hypotheses={"needs_claim_guidance": 0.92},
        active_mission={
            "type": "auto_claim_guidance",
            "goal": "orientar correctamente al usuario",
            "status": "in_progress",
            "missing": ["injuries", "user_role"],
            "blockers": ["injuries_unknown"],
        },
        tool_evidence={"cleas": {"name": "CLEAS"}},
        context_bundle={
            "mission": {"type": "auto_claim_guidance"},
            "relevant_memory": {"last_event_type": "vehicle_collision"},
            "domain_context": {"domain": "insurance"},
        },
    )

    conversation = ConversationState.from_cognitive_state(state, turn_count=2)

    assert conversation.conversation_id == "contract-runtime"
    assert conversation.turn_count == 2
    assert conversation.focus["active_mission_type"] == "auto_claim_guidance"
    assert conversation.slots["injuries"]["status"] == "pending"
    assert conversation.slots["injuries"]["blocker"] == "injuries_unknown"
    assert "zero_cost_execution_plan" not in conversation.confirmed_facts
    assert "runtime_execution_engine" not in conversation.confirmed_facts
    assert conversation.confirmed_facts["event_type"] == "vehicle_collision"
    assert conversation.confirmed_facts["entity.event"] == "vehicle_collision"
    assert conversation.active_hypotheses["needs_claim_guidance"] == 0.92
    assert conversation.relevant_evidence["cleas"]["name"] == "CLEAS"
    assert conversation.derived_state["zero_cost_execution_plan"]["flow"] == "guided_process"
    assert conversation.derived_state["runtime_execution_engine"]["official_engine"] == "runtime_executor"


def test_public_conversation_state_projects_to_canonical_contract_with_product_state_separated():
    state = PublicConversationState(
        conversation_id="public-contract",
        turn_count=4,
        active_goal="saber_que_documentacion_corresponde",
        active_topic="siniestro",
        active_claim_type="choque",
        known_facts=("tipo_siniestro:choque", "denuncia_cargada"),
        missing_facts=("injuries",),
        interaction_signals={"frustration": "medium"},
        next_action_suggested="Responder documentacion contextual.",
        last_category="claim_documentation",
        fallback_count=1,
    )
    semantic = SemanticParse(
        intent="consultar_documentacion",
        topic="siniestro",
        user_goal="saber_que_documentacion_corresponde",
        known_facts=("tipo_siniestro:choque",),
        missing_facts=("user_role",),
        signals=InteractionSignals(frustration="medium", urgency="low"),
        confidence=0.84,
        entities={"claim_type": "choque"},
        refers_to_previous=True,
    )
    planner = PlannerDecision(next_action="answer", strategy="answer_with_contextual_guidance")
    supervisor = SupervisorResult(passes=True)

    conversation = state.to_conversation_state(
        semantic_parse=semantic.to_dict(),
        planner_decision=planner.to_dict(),
        supervisor_result=supervisor.to_dict(),
    )

    assert conversation.focus["active_topic"] == "siniestro"
    assert conversation.focus["active_claim_type"] == "choque"
    assert conversation.confirmed_facts["tipo_siniestro"] == "choque"
    assert conversation.confirmed_facts["denuncia_cargada"] is True
    assert set(conversation.slots) == {"injuries", "user_role"}
    assert conversation.conversational_strategy["strategy"] == "answer_with_contextual_guidance"
    assert conversation.user_signals["frustration"] == "medium"
    assert conversation.last_conversational_act["type"] == "consultar_documentacion"
    assert conversation.product_state["last_category"] == "claim_documentation"
    assert conversation.product_state["fallback_count"] == 1
    assert conversation.derived_state["semantic_parse"]["intent"] == "consultar_documentacion"
    assert conversation.derived_state["supervisor_result"]["passes"] is True


def test_context_bundle_projects_as_derived_context_not_persistent_state():
    bundle = ContextBundle(
        mission={"type": "auto_claim_guidance", "goal": "orientar", "missing": ["injuries"]},
        facts={"event_type": "vehicle_collision"},
        hypotheses={"needs_claim_guidance": 0.92},
        plan=["ask_if_injuries"],
        relevant_memory={"last_event_type": "vehicle_collision"},
        tool_evidence={"cleas": {"name": "CLEAS"}},
        domain_context={"domain": "insurance"},
    )

    conversation = bundle.to_conversation_state(conversation_id="ctx", turn_count=3)

    assert conversation.conversation_id == "ctx"
    assert conversation.focus["active_mission_type"] == "auto_claim_guidance"
    assert conversation.slots["injuries"]["status"] == "pending"
    assert conversation.confirmed_facts["event_type"] == "vehicle_collision"
    assert conversation.relevant_context["relevant_memory"]["last_event_type"] == "vehicle_collision"
    assert conversation.derived_state["context_bundle"]["plan"] == ["ask_if_injuries"]


def test_runtime_and_conversation_manager_remain_compatible_with_contract_projection():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Me chocaron ayer", metadata={"conversation_id": "contract-runtime"}))
    projection = runtime.conversation_manager.conversation_state("contract-runtime")

    assert state.response
    assert projection.contract == "conversation_state.v1"
    assert projection.conversation_id == "contract-runtime"
    assert projection.turn_count == 1
    assert projection.active_mission
    assert "conversation_manager.operational_owner" in projection.projection_sources


def test_conversation_state_projects_back_to_cognitive_state_as_legacy_carrier():
    conversation = ConversationState(
        conversation_id="operational-contract",
        turn_count=3,
        active_mission={"type": "auto_claim_guidance", "goal": "orientar", "missing": ["injuries"]},
        confirmed_facts={"event_type": "vehicle_collision"},
        active_hypotheses={"needs_claim_guidance": 0.92},
        relevant_evidence={"cleas": {"name": "CLEAS"}},
    )

    carrier = conversation.to_cognitive_state()

    assert carrier.conversation_id == "operational-contract"
    assert carrier.active_mission["type"] == "auto_claim_guidance"
    assert carrier.facts["event_type"] == "vehicle_collision"
    assert carrier.hypotheses["needs_claim_guidance"] == 0.92
    assert carrier.tool_evidence["cleas"]["name"] == "CLEAS"


def test_mission_manager_loads_active_mission_from_conversation_state():
    mission = {"type": "auto_claim_guidance", "goal": "orientar", "missing": ["injuries"]}
    conversation = ConversationState(conversation_id="mission-owner", active_mission=mission)
    manager = MissionManager()

    state = manager.before_kernel(
        Event(type="user_message", payload="hola", metadata={"conversation_id": "mission-owner"}),
        CognitiveState(conversation_id="mission-owner"),
        conversation_state=conversation,
    )

    assert state.active_mission == mission
    assert state.timeline[-1]["operation"] == "MISSION_LOAD_FROM_CONVERSATION_STATE"


def test_public_conversation_state_can_be_projected_from_canonical_contract():
    conversation = ConversationState(
        conversation_id="public-view",
        turn_count=5,
        focus={"active_topic": "siniestro", "active_claim_type": "choque", "active_case_id": "ABC"},
        goals=[{"name": "orientar_siniestro", "status": "active"}],
        slots={"injuries": {"status": "pending"}, "user_role": {"status": "filled"}},
        confirmed_facts={"tipo_siniestro": "choque", "denuncia_cargada": True, "entity.event": "vehicle_collision"},
        conversational_strategy={"next_action": "answer"},
        last_conversational_act={"category": "claim_guidance"},
        user_signals={"frustration": "low"},
        product_state={"fallback_count": 2, "confusion_count": 1, "last_response_signature": "firma"},
    )

    public_view = PublicConversationState.from_conversation_state(conversation)

    assert public_view.conversation_id == "public-view"
    assert public_view.turn_count == 5
    assert public_view.active_topic == "siniestro"
    assert public_view.active_claim_type == "choque"
    assert public_view.active_case_id == "ABC"
    assert public_view.active_goal == "orientar_siniestro"
    assert public_view.missing_facts == ("injuries",)
    assert "tipo_siniestro:choque" in public_view.known_facts
    assert "denuncia_cargada" in public_view.known_facts
    assert public_view.interaction_signals == {"frustration": "low"}
    assert public_view.fallback_count == 2
