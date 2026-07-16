import json

import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.core.state import CognitiveState
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.context_manager import ContextManager
from aca_os.conversation_objective import (
    CONVERSATION_FIRST_MODE,
    LEGACY_RESPONSE_MODE,
    ConversationObjectiveProjector,
    ConversationalFirstConfig,
    ObjectiveDeterministicRealizer,
)
from aca_os.conversation_state import ConversationState
from aca_os.conversational_first_evaluation import (
    load_conversational_first_benchmark,
    run_conversational_first_benchmark,
)
from aca_os.llm_verbalization import (
    LLMProviderRequest,
    LLMProviderResponse,
    LLMProviderTimeout,
    LLMVerbalizationConfig,
    LLMVerbalizer,
)
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyManager
from aca_os.step_handlers import OutputStepHandler, StepExecutionContext, StepRuntimeServices, step_from_plan
from aca_os.step_handlers import build_default_step_handler_registry
from aca_os.tool_engine import ToolEngine
from sdk.factory import build_galicia_runtime
from zero_cost.execution_plan import ExecutionPlan


class _Provider:
    provider_name = "test"

    def __init__(self, response="", error=None):
        self.response = response
        self.error = error
        self.last_request = None
        self.requests = []

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        self.last_request = request
        self.requests.append(request)
        if self.error:
            raise self.error
        return LLMProviderResponse(
            text=self.response,
            provider=self.provider_name,
            model=request.model,
            request_id="conversation-first-test",
        )


class _FailingProjector:
    def project(self, **kwargs):
        raise ValueError("objective_projection_failed")


def _llm_config(**changes):
    values = {
        "enabled": True,
        "provider": "openai",
        "model": "test-model",
        "api_key": "test-key",
        "validation_mode": "strict",
    }
    values.update(changes)
    return LLMVerbalizationConfig(**values)


def _execution_plan():
    return ExecutionPlan.from_flow(
        {
            "flow": "fallback",
            "source_action": "fallback_response",
            "steps": ["output"],
            "payload": {},
        }
    )


def _services():
    return StepRuntimeServices(
        policy_manager=PolicyManager(),
        tool_engine=ToolEngine(),
        compiler=GraphCompiler(),
        kernel=ACAKernel(build_default_registry()),
        mission_manager=MissionManager(),
        memory_engine=MemoryEngine(),
        context_manager=ContextManager(),
    )


def _structured_state():
    facts = {
        "conversation_goal": {
            "goal": {"intention": "respond_to_pending_answer", "priority": 70},
            "authority": {
                "semantic_primary_goal": {
                    "type": "achieve_user_outcome",
                    "target": "Quiero dar de baja internet.",
                    "priority": 1,
                    "confidence": 0.94,
                }
            },
        },
        "conversation_response_plan": {
            "plan": {
                "primary_user_need": {"key": "understand_user_need", "confidence": 0.45},
                "dominant_concern": {"key": "understand_user_need", "confidence": 0.45},
                "required_information": [{"slot": "user_need", "question": "Qué necesitás?"}],
                "next_action": {"type": "ask_justified_question"},
            }
        },
        "conversation_plan": {
            "plan": {
                "active_plan": {
                    "current_step": {"id": "understand_user_need", "type": "clarification"}
                }
            }
        },
    }
    return CognitiveState(
        response="¿Tenés toda la documentación del siniestro?",
        facts=facts,
    )


def _semantic_context():
    representation = {
        "language": "es",
        "semantic_segments": [{"text": "Quiero dar de baja internet.", "kind": "statement"}],
        "intents": [{"type": "cancel_service", "confidence": 0.94}],
        "goals": [
            {
                "type": "achieve_user_outcome",
                "target": "Quiero dar de baja internet.",
                "priority": 1,
                "confidence": 0.94,
            }
        ],
        "assertions": [],
        "constraints": [],
        "topic_structure": {"primary_topic": "connectivity"},
    }
    projection = {
        "goal_projection": {"goals": representation["goals"]},
        "intent_projection": {"intent": "cancel_service", "confidence": 0.94},
    }
    return representation, projection


def _context(handler_state=None):
    state = handler_state or _structured_state()
    plan = _execution_plan()
    representation, projection = _semantic_context()
    return StepExecutionContext(
        state=state,
        event=Event(type="user_message", payload="Quiero dar de baja internet."),
        execution_plan=plan,
        step=step_from_plan(plan, "output"),
        services=_services(),
        conversation_state=ConversationState(),
        runtime_context={
            "semantic_representation": representation,
            "semantic_projection": projection,
        },
    )


def test_conversation_objective_is_language_free_immutable_and_suppresses_redundant_user_need():
    representation, projection = _semantic_context()
    objective = ConversationObjectiveProjector().project(
        state=_structured_state(),
        execution_plan=_execution_plan(),
        conversation_state=ConversationState(),
        semantic_representation=representation,
        semantic_projection=projection,
    )

    serialized = json.dumps(objective.to_dict(), ensure_ascii=False)
    assert objective.valid is True
    assert objective.goal["type"] == "achieve_user_outcome"
    assert objective.missing_information == ()
    assert objective.next_step["action"] == "converse"
    assert "Quiero dar de baja internet" not in serialized
    assert "documentación" not in serialized
    with pytest.raises(TypeError):
        objective.goal["type"] = "different"


def test_conversational_first_output_uses_objective_instead_of_kernel_or_composer_text():
    candidate = "Entiendo, querés dar de baja el servicio de internet. Puedo ayudarte con eso."
    provider = _Provider(candidate)
    handler = OutputStepHandler(
        llm_verbalizer=LLMVerbalizer(config=_llm_config(), provider=provider),
        conversational_first_config=ConversationalFirstConfig(enabled=True),
    )

    result = handler.execute(_context())

    authority = result.outcome["result"]["conversation_authority"]
    objective = result.outcome["result"]["conversation_objective"]
    prompt = json.loads(provider.last_request.input_text)
    assert result.state.response == candidate
    assert authority["authority_mode"] == CONVERSATION_FIRST_MODE
    assert authority["legacy_response"] != result.state.response
    assert objective["objective"]["next_step"]["action"] == "converse"
    assert prompt["content_authority"] == "conversation_objective"
    assert "source_response" not in prompt
    assert prompt["semantic_context"]["goals"][0]["target"] == "Quiero dar de baja internet."
    assert "documentación del siniestro" not in result.state.response


def test_provider_failure_uses_objective_fallback_not_legacy_domain_template():
    handler = OutputStepHandler(
        llm_verbalizer=LLMVerbalizer(
            config=_llm_config(),
            provider=_Provider(error=LLMProviderTimeout("timeout")),
        ),
        conversational_first_config=ConversationalFirstConfig(enabled=True),
    )

    result = handler.execute(_context())

    assert result.state.response == "Entiendo. Sigamos con lo que necesitás resolver."
    assert result.state_changes["conversation_authority_mode"] == CONVERSATION_FIRST_MODE
    assert result.state_changes["llm_execution"]["fallback_reason"] == "provider_timeout"
    assert "documentación" not in result.state.response.lower()
    assert "siniestro" not in result.state.response.lower()


def test_invalid_objective_rolls_back_atomically_to_legacy_response():
    state = _structured_state()
    verbalizer = LLMVerbalizer(config=_llm_config(enabled=False, api_key=""))
    handler = OutputStepHandler(
        llm_verbalizer=verbalizer,
        conversational_first_config=ConversationalFirstConfig(enabled=True),
        objective_projector=_FailingProjector(),
    )

    result = handler.execute(_context(state))

    assert result.state.response == state.response
    assert result.state_changes["conversation_authority_mode"] == LEGACY_RESPONSE_MODE
    assert result.state_changes["conversation_authority_rollback"] == "objective_projection_failed"
    assert "conversation_objective" not in result.state.facts


def test_legacy_mode_remains_the_default_and_preserves_existing_output():
    state = _structured_state()
    handler = OutputStepHandler(
        llm_verbalizer=LLMVerbalizer(config=_llm_config(enabled=False, api_key="")),
        conversational_first_config=ConversationalFirstConfig(enabled=False),
    )

    result = handler.execute(_context(state))

    assert result.state.response == state.response
    assert result.state_changes["conversation_authority_mode"] == LEGACY_RESPONSE_MODE


def test_runtime_transports_semantic_context_to_the_objective_output_boundary():
    provider = _Provider(
        "Entiendo, querés dar de baja el servicio de internet. Puedo ayudarte con eso."
    )
    registry = build_default_step_handler_registry()
    registry.register(
        OutputStepHandler(
            llm_verbalizer=LLMVerbalizer(config=_llm_config(), provider=provider),
            conversational_first_config=ConversationalFirstConfig(enabled=True),
        )
    )
    runtime = build_galicia_runtime()
    runtime.step_handlers = registry
    runtime.legacy_runtime.handlers = registry

    state = runtime.process(
        Event(
            type="user_message",
            payload="Quiero dar de baja internet.",
            metadata={"conversation_id": "conversation-first-runtime"},
        )
    )

    outcome = state.facts["execution_step_outcomes"][-1]
    prompts = [json.loads(request.input_text) for request in provider.requests]
    assert state.response == provider.response
    assert state.facts["conversation_objective"]["authority_mode"] == CONVERSATION_FIRST_MODE
    assert outcome["state_changes"]["conversation_authority_mode"] == CONVERSATION_FIRST_MODE
    assert any(prompt.get("semantic_context", {}).get("goals") for prompt in prompts)
    assert all("source_response" not in prompt for prompt in prompts)


def test_conversational_first_configuration_is_explicit_and_reversible():
    assert ConversationalFirstConfig.from_env({}).enabled is False
    assert ConversationalFirstConfig.from_env({"ACA_CONVERSATIONAL_FIRST_ENABLED": "true"}).enabled is True


def test_conversational_first_benchmark_is_permanent_reproducible_and_green():
    suite = load_conversational_first_benchmark()
    first = run_conversational_first_benchmark()
    second = run_conversational_first_benchmark()

    assert suite["scenario_count"] >= 9
    assert first == second
    assert first["passed"] is True
    assert first["metrics"]["objective_validity_percentage"] == 100.0
    assert first["metrics"]["domain_contamination_absence_percentage"] == 100.0
    assert first["metrics"]["legacy_replacement_percentage"] == 100.0
