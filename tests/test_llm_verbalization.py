import json
import socket
from urllib.error import URLError

from aca_kernel.core.events import Event
from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.core.state import CognitiveState
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.context_manager import ContextManager
from aca_os.llm_verbalization import (
    DeterministicVerbalizationValidator,
    LLMProviderRequest,
    LLMProviderResponse,
    LLMProviderTimeout,
    LLMProviderFactory,
    LLMVerbalizationConfig,
    LLMVerbalizer,
    OllamaAdapter,
    OpenAIResponsesAdapter,
    VerbalizationBrief,
    warmup_default_llm_provider,
)
from aca_os.step_handlers import (
    OutputStepHandler,
    StepExecutionContext,
    build_default_step_handler_registry,
    step_from_plan,
)
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyManager
from aca_os.tool_engine import ToolEngine
from aca_os.verbalization_evaluation import (
    load_language_realization_benchmark,
    load_llm_verbalization_benchmark,
    render_language_realization_benchmark_report,
    render_llm_verbalization_benchmark_report,
    render_llm_verbalization_provider_comparison,
    run_language_realization_benchmark,
    run_llm_verbalization_benchmark,
    run_llm_verbalization_provider_comparison,
)
from sdk.factory import build_galicia_runtime
from zero_cost.execution_plan import ExecutionPlan

class _Provider:
    provider_name = "test"

    def __init__(self, response: str = "", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = 0
        self.last_request = None

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        self.calls += 1
        self.last_request = request
        if self.error:
            raise self.error
        return LLMProviderResponse(
            text=self.response,
            provider=self.provider_name,
            model=request.model,
            request_id="test-request",
        )


def _config(**changes):
    values = {
        "enabled": True,
        "provider": "openai",
        "model": "test-model",
        "api_key": "test-key",
        "validation_mode": "strict",
    }
    values.update(changes)
    return LLMVerbalizationConfig(**values)


def _brief(**changes):
    values = {
        "deterministic_response": (
            "Que necesitas resolver primero? Asi puedo responder primero la preocupacion mas importante."
        ),
        "user_message": "Hola, necesito ayuda.",
        "selected_operation": {"flow": "fallback", "action": "fallback_response"},
    }
    values.update(changes)
    return VerbalizationBrief(**values)


def _plan():
    return ExecutionPlan.from_flow(
        {
            "flow": "fallback",
            "source_action": "fallback_response",
            "steps": ["output"],
            "payload": {},
        }
    )


def _services():
    from aca_os.step_handlers import StepRuntimeServices

    return StepRuntimeServices(
        policy_manager=PolicyManager(),
        tool_engine=ToolEngine(),
        compiler=GraphCompiler(),
        kernel=ACAKernel(build_default_registry()),
        mission_manager=MissionManager(),
        memory_engine=MemoryEngine(),
        context_manager=ContextManager(),
    )


def test_llm_configuration_is_explicit_and_does_not_expose_api_key():
    config = LLMVerbalizationConfig.from_env(
        {
            "LLM_ENABLED": "true",
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "configured-model",
            "LLM_TIMEOUT": "4.5",
            "LLM_TEMPERATURE": "0.1",
            "LLM_MAX_TOKENS": "180",
            "LLM_VALIDATION_MODE": "strict",
            "OPENAI_API_KEY": "secret",
        }
    )

    assert config.enabled is True
    assert config.model == "configured-model"
    assert config.timeout_seconds == 4.5
    assert config.max_tokens == 180
    assert config.unavailable_reason() is None
    assert "api_key" not in config.observable()
    assert "secret" not in repr(config)


def test_invalid_numeric_configuration_falls_back_to_safe_defaults():
    config = LLMVerbalizationConfig.from_env(
        {
            "LLM_ENABLED": "true",
            "LLM_TIMEOUT": "invalid",
            "LLM_TEMPERATURE": "invalid",
            "LLM_MAX_TOKENS": "invalid",
        }
    )

    assert config.timeout_seconds == 60.0
    assert config.temperature == 0.2
    assert config.max_tokens == 300


def test_no_api_key_uses_deterministic_fallback_without_calling_provider():
    provider = _Provider("Una respuesta que no debe usarse.")
    verbalizer = LLMVerbalizer(
        config=_config(api_key=""),
        provider=provider,
    )

    result = verbalizer.verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "missing_api_key"
    assert result.provider_called is False
    assert provider.calls == 0


def test_provider_timeout_uses_deterministic_fallback():
    provider = _Provider(error=LLMProviderTimeout("timeout"))
    result = LLMVerbalizer(config=_config(), provider=provider).verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "provider_timeout"
    assert result.provider_called is True


def test_valid_provider_response_is_used_as_visible_response():
    candidate = "Hola. Contame un poco mas que necesitas resolver y vemos juntos como ayudarte?"
    provider = _Provider(candidate)
    result = LLMVerbalizer(config=_config(), provider=provider).verbalize(_brief())

    assert result.accepted is True
    assert result.final_response == candidate
    assert result.validation.accepted is True
    assert provider.calls == 1
    assert "source_response" in provider.last_request.input_text
    assert "ACA already decided the content" in provider.last_request.instructions
    assert "preserve meaning, not wording" in provider.last_request.instructions.lower()
    assert "Write a fresh" in provider.last_request.instructions
    assert "Never add knowledge" in provider.last_request.instructions


def test_hallucinated_fact_operation_and_permission_are_rejected():
    provider = _Provider("Ya cree un ticket 987 y esta aprobado.")
    result = LLMVerbalizer(config=_config(), provider=provider).verbalize(_brief())

    assert result.accepted is False
    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "validation_failed"
    assert {
        "numeric_grounding",
        "operational_grounding",
        "execution_grounding",
        "permission_grounding",
    }.issubset(set(result.validation.rejection_reasons))


def test_invented_identity_fact_is_rejected():
    provider = _Provider("Tu nombre es Nicolas. En que puedo ayudarte?")
    result = LLMVerbalizer(config=_config(), provider=provider).verbalize(_brief())

    assert result.accepted is False
    assert "factual_grounding" in result.validation.rejection_reasons


def test_candidate_work_case_state_governance_and_tools_are_read_only():
    brief = _brief(
        candidate_work={"operation": "prepare_claim_follow_up", "status": "pending"},
        case_state={"case_stage": "waiting_review", "documentation": "complete"},
        governance={"execution_allowed": False, "requires_confirmation": True},
        policy={"decision": "ALLOW", "modifications": []},
        executed_tools=({"tool": "claim_status", "executed": False},),
    )
    before = brief.prompt_payload()
    provider = _Provider("Hola. Contame un poco mas que necesitas resolver y vemos juntos como ayudarte?")

    result = LLMVerbalizer(config=_config(), provider=provider).verbalize(brief)

    assert result.accepted is True
    assert brief.prompt_payload() == before
    payload = json.loads(provider.last_request.input_text)
    assert "current_user_message" not in payload
    assert payload["output_constraints"] == {
        "question_count": 1,
        "maximum_sentences": 2,
        "source_is_content_authority": True,
    }
    assert payload["candidate_work"] == before["candidate_work"]
    assert payload["case_state"] == before["case_state"]
    assert payload["governance_constraints"] == before["governance_constraints"]
    assert payload["executed_tools"] == before["executed_tools"]


def test_selected_question_cannot_be_replaced_by_a_different_question():
    brief = _brief(
        deterministic_response="Necesito confirmar una cosa. Hubo lesionados?",
        pending_information=(
            {
                "slot": "injuries",
                "question": "Hubo lesionados?",
                "purpose": "definir si corresponde priorizar asistencia",
            },
        ),
    )
    validation = DeterministicVerbalizationValidator().validate(
        candidate="Para continuar, cual es tu DNI?",
        brief=brief,
        mode="strict",
    )

    assert validation.accepted is False
    assert "selected_question_preserved" in validation.rejection_reasons


def test_output_handler_records_deterministic_candidate_validation_and_final_response():
    candidate = "Hola. Contame un poco mas que necesitas resolver y vemos juntos como ayudarte?"
    verbalizer = LLMVerbalizer(config=_config(), provider=_Provider(candidate))
    handler = OutputStepHandler(llm_verbalizer=verbalizer)
    plan = _plan()
    state = CognitiveState(response=_brief().deterministic_response)

    result = handler.execute(
        StepExecutionContext(
            state=state,
            event=Event(type="user_message", payload="Hola, necesito ayuda."),
            execution_plan=plan,
            step=step_from_plan(plan, "output"),
            services=_services(),
        )
    )

    trace = result.outcome["result"]["llm_verbalization"]
    assert result.state.response == candidate
    assert trace["deterministic_response"] == state.response
    assert trace["verbalized_response"] == candidate
    assert trace["validation"]["accepted"] is True
    assert trace["response_sent"] == candidate
    assert result.state_changes["llm_response_accepted"] is True
    assert result.state_changes["llm_execution"]["provider"] == "test"
    assert result.state_changes["llm_execution"]["model"] == "test-model"
    assert result.state_changes["llm_execution"]["cache_hit"] is False
    assert result.state_changes["llm_execution"]["fallback_reason"] is None
    assert result.state_changes["llm_execution"]["latency_ms"] >= 0.0


def test_output_handler_preserves_operational_and_tool_contract_records():
    candidate = "Hola. Contame un poco mas que necesitas resolver y vemos juntos como ayudarte?"
    handler = OutputStepHandler(
        llm_verbalizer=LLMVerbalizer(config=_config(), provider=_Provider(candidate))
    )
    plan = _plan()
    protected_facts = {
        "candidate_work": {"operation": "prepare_handoff", "status": "pending"},
        "case_state_projection": {"case_stage": "waiting_user"},
        "operational_governance": {"execution_allowed": False, "requires_confirmation": True},
        "tool_contracts": {
            "handoff": {
                "deterministic": True,
                "has_side_effects": False,
                "supports_dry_run": True,
            }
        },
    }
    state = CognitiveState(response=_brief().deterministic_response, facts=protected_facts)

    result = handler.execute(
        StepExecutionContext(
            state=state,
            event=Event(type="user_message", payload="Hola, necesito ayuda."),
            execution_plan=plan,
            step=step_from_plan(plan, "output"),
            services=_services(),
        )
    )

    assert result.state.facts == protected_facts
    assert result.state.selected_program == state.selected_program
    assert result.state.policy_result == state.policy_result
    assert result.state.tool_evidence == state.tool_evidence


def test_user_message_scopes_cache_without_becoming_provider_content():
    first = _brief(user_message="Primer contexto")
    second = _brief(user_message="Segundo contexto")

    assert first.prompt_payload() == second.prompt_payload()
    assert first.fingerprint() != second.fingerprint()


def test_verbalizer_cache_prevents_duplicate_provider_calls_for_runtime_comparison():
    provider = _Provider("Hola. Contame un poco mas que necesitas resolver y vemos juntos como ayudarte?")
    verbalizer = LLMVerbalizer(config=_config(), provider=provider)
    brief = _brief()

    first = verbalizer.verbalize(brief)
    second = verbalizer.verbalize(brief)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.provider_called is False
    assert first.final_response == second.final_response
    assert provider.calls == 1


def test_runtime_uses_llm_verbalization_without_changing_cognitive_authority():
    candidate = (
        "Entiendo la demora. Como la denuncia sigue en tramite despues de una semana, conviene "
        "revisar que esta frenando el avance. Alguien resulto lesionado o necesito asistencia?"
    )
    provider = _Provider(candidate)
    registry = build_default_step_handler_registry()
    registry.register(OutputStepHandler(llm_verbalizer=LLMVerbalizer(config=_config(), provider=provider)))
    runtime = build_galicia_runtime()
    runtime.step_handlers = registry
    runtime.legacy_runtime.handlers = registry

    state = runtime.process(
        Event(
            type="user_message",
            payload="Cargue una denuncia desde la app y hace una semana sigue en tramite.",
            metadata={"conversation_id": "llm-integration"},
        )
    )

    output = state.facts["execution_step_outcomes"][-1]
    assert state.response == candidate
    assert state.selected_program == "auto_claim_guidance"
    assert state.facts["zero_cost_execution_plan"]["flow"] == "guided_process"
    assert state.policy_result["decision"] == "ALLOW"
    assert output["result"]["llm_verbalization"]["accepted"] is True
    assert provider.calls == 1


def test_openai_adapter_uses_responses_api_and_extracts_output(monkeypatch):
    captured = {}

    class _HTTPResponse:
        headers = {"x-request-id": "request-123"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "resp-123",
                    "model": "test-model",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "Respuesta natural."}],
                        }
                    ],
                }
            ).encode("utf-8")

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _HTTPResponse()

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _urlopen)
    response = OpenAIResponsesAdapter(api_key="secret").generate(
        LLMProviderRequest(
            model="test-model",
            instructions="Only rewrite.",
            input_text="input",
            timeout_seconds=3.0,
            temperature=0.1,
            max_tokens=100,
        )
    )

    assert captured["url"].endswith("/v1/responses")
    assert captured["authorization"] == "Bearer secret"
    assert captured["payload"]["max_output_tokens"] == 100
    assert response.text == "Respuesta natural."
    assert response.request_id == "request-123"


def test_ollama_configuration_uses_offline_defaults():
    config = LLMVerbalizationConfig.from_env(
        {
            "LLM_ENABLED": "true",
            "LLM_PROVIDER": "ollama",
        }
    )

    assert config.provider == "ollama"
    assert config.model == "qwen3:8b"
    assert config.timeout_seconds == 60.0
    assert config.ollama_host == "http://localhost:11434"
    assert config.ollama_keep_alive == "5m"
    assert config.ollama_warmup_on_start is False
    assert config.unavailable_reason() is None
    assert config.observable()["ollama_host"] == "http://localhost:11434"


def test_ollama_runtime_readiness_configuration_respects_environment_overrides():
    config = LLMVerbalizationConfig.from_env(
        {
            "LLM_ENABLED": "true",
            "LLM_PROVIDER": "ollama",
            "LLM_TIMEOUT": "75",
            "OLLAMA_KEEP_ALIVE": "12m",
            "OLLAMA_WARMUP_ON_START": "true",
        }
    )

    assert config.timeout_seconds == 75.0
    assert config.ollama_keep_alive == "12m"
    assert config.ollama_warmup_on_start is True
    assert config.observable()["ollama_keep_alive"] == "12m"
    assert config.observable()["ollama_warmup_on_start"] is True


def test_provider_factory_resolves_openai_ollama_and_registered_provider():
    factory = LLMProviderFactory.default()
    openai = factory.create(_config())
    ollama = factory.create(_config(provider="ollama", model="qwen3:8b"))
    custom = _Provider("custom")
    custom.provider_name = "custom"
    factory.register("custom", lambda config: custom)

    assert isinstance(openai, OpenAIResponsesAdapter)
    assert isinstance(ollama, OllamaAdapter)
    assert factory.create(_config(provider="custom")) is custom
    assert factory.supported_providers() == ("custom", "ollama", "openai")

    result = LLMVerbalizer(
        config=_config(provider="custom"),
        provider_factory=factory,
    ).verbalize(_brief())
    assert result.provider == "custom"
    assert result.accepted is False
    assert result.fallback_reason == "validation_failed"


def test_ollama_adapter_detects_model_and_generates_over_http(monkeypatch):
    requests = []

    class _Response:
        headers = {}

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def _urlopen(request, timeout):
        requests.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "payload": json.loads(request.data.decode("utf-8")) if request.data else {},
                "timeout": timeout,
            }
        )
        if request.full_url.endswith("/api/tags"):
            return _Response({"models": [{"name": "qwen3:8b", "model": "qwen3:8b"}]})
        return _Response(
            {
                "model": "qwen3:8b",
                "created_at": "2026-07-14T00:00:00Z",
                "response": "Respuesta natural local.",
                "done": True,
            }
        )

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _urlopen)
    response = OllamaAdapter().generate(
        LLMProviderRequest(
            model="qwen3:8b",
            instructions="Only rewrite.",
            input_text="input",
            timeout_seconds=3.0,
            temperature=0.1,
            max_tokens=100,
        )
    )

    assert [request["url"] for request in requests] == [
        "http://localhost:11434/api/tags",
        "http://localhost:11434/api/generate",
    ]
    assert requests[1]["payload"]["stream"] is False
    assert requests[1]["payload"]["think"] is False
    assert requests[1]["payload"]["keep_alive"] == "5m"
    assert requests[1]["payload"]["options"] == {"num_predict": 100, "temperature": 0.1}
    assert response.text == "Respuesta natural local."
    assert response.provider == "ollama"


def test_ollama_warmup_uses_empty_prompt_and_configured_keep_alive(monkeypatch):
    captured = {}

    class _Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "qwen3:8b",
                    "done": True,
                    "done_reason": "load",
                    "total_duration": 12_000_000_000,
                    "load_duration": 11_500_000_000,
                }
            ).encode("utf-8")

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _urlopen)
    result = OllamaAdapter(keep_alive="9m").warmup(
        model="qwen3:8b",
        timeout_seconds=60.0,
    )

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["payload"] == {
        "model": "qwen3:8b",
        "prompt": "",
        "stream": False,
        "keep_alive": "9m",
    }
    assert captured["timeout"] == 60.0
    assert result["model_loaded"] is True
    assert result["done_reason"] == "load"


def test_optional_ollama_warmup_runs_once_and_records_readiness():
    class _WarmupProvider:
        provider_name = "ollama"

        def __init__(self):
            self.calls = 0

        def warmup(self, *, model, timeout_seconds):
            self.calls += 1
            return {"model": model, "model_loaded": True, "load_duration_ns": 1}

    provider = _WarmupProvider()
    config = _config(
        provider="ollama",
        model="aca-203-warmup-once",
        api_key="",
        ollama_host="http://localhost:11434",
        ollama_keep_alive="5m",
        ollama_warmup_on_start=True,
    )

    first = warmup_default_llm_provider(config=config, provider=provider)
    second = warmup_default_llm_provider(config=config, provider=provider)

    assert provider.calls == 1
    assert first == second
    assert first["warmup_executed"] is True
    assert first["status"] == "success"
    assert first["model_loaded"] is True
    assert first["timeout_seconds"] == 60.0
    assert first["keep_alive"] == "5m"


def test_failed_ollama_warmup_never_prevents_startup():
    class _FailingWarmupProvider:
        provider_name = "ollama"

        def warmup(self, *, model, timeout_seconds):
            raise LLMProviderTimeout("cold load timeout")

    config = _config(
        provider="ollama",
        model="aca-203-warmup-failure",
        api_key="",
        ollama_warmup_on_start=True,
    )

    event = warmup_default_llm_provider(
        config=config,
        provider=_FailingWarmupProvider(),
    )

    assert event["warmup_executed"] is True
    assert event["status"] == "failed"
    assert event["model_loaded"] is False
    assert event["failure_reason"] == "provider_timeout"


def test_ollama_unavailable_falls_back_without_exception(monkeypatch):
    def _unavailable(request, timeout):
        raise URLError(ConnectionRefusedError("not running"))

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _unavailable)
    verbalizer = LLMVerbalizer(config=_config(provider="ollama", model="qwen3:8b"))

    result = verbalizer.verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.provider == "ollama"
    assert result.model == "qwen3:8b"
    assert result.fallback_reason == "ollama_unavailable"
    assert result.provider_called is True


def test_ollama_direct_socket_failure_is_reported_as_unavailable(monkeypatch):
    def _unavailable(request, timeout):
        raise ConnectionRefusedError("not running")

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _unavailable)
    result = LLMVerbalizer(
        config=_config(provider="ollama", model="qwen3:8b")
    ).verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "ollama_unavailable"


def test_ollama_timeout_falls_back_deterministically(monkeypatch):
    def _timeout(request, timeout):
        raise socket.timeout("slow local model")

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _timeout)
    result = LLMVerbalizer(
        config=_config(provider="ollama", model="qwen3:8b")
    ).verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "provider_timeout"


def test_ollama_missing_model_falls_back_with_specific_reason(monkeypatch):
    class _Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"models": [{"name": "llama3:8b"}]}'

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", lambda request, timeout: _Response())
    result = LLMVerbalizer(
        config=_config(provider="ollama", model="qwen3:8b")
    ).verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "ollama_model_not_found"


def test_invalid_ollama_host_never_attempts_http(monkeypatch):
    calls = []
    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", lambda *args, **kwargs: calls.append(args))
    config = LLMVerbalizationConfig.from_env(
        {
            "LLM_ENABLED": "true",
            "LLM_PROVIDER": "ollama",
            "OLLAMA_HOST": "not-a-url",
        }
    )

    result = LLMVerbalizer(config=config).verbalize(_brief())

    assert result.final_response == result.deterministic_response
    assert result.fallback_reason == "invalid_ollama_host"
    assert result.provider_called is False
    assert calls == []


def test_ollama_uses_same_validator_and_provider_independent_cache(monkeypatch):
    calls = []
    candidate = "Hola. Contame un poco mas que necesitas resolver y vemos juntos como ayudarte?"

    class _Response:
        headers = {}

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def _urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith("/api/tags"):
            return _Response({"models": [{"name": "qwen3:8b"}]})
        return _Response({"model": "qwen3:8b", "response": candidate, "done": True})

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _urlopen)
    verbalizer = LLMVerbalizer(config=_config(provider="ollama", model="qwen3:8b"))

    first = verbalizer.verbalize(_brief())
    second = verbalizer.verbalize(_brief())

    assert first.accepted is True
    assert first.final_response == candidate
    assert second.cache_hit is True
    assert second.provider_called is False
    assert len(calls) == 2


def test_ollama_validation_failure_uses_same_deterministic_fallback(monkeypatch):
    class _Response:
        headers = {}

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def _urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _Response({"models": [{"name": "qwen3:8b"}]})
        return _Response(
            {"model": "qwen3:8b", "response": "Ya cree un ticket 987.", "done": True}
        )

    monkeypatch.setattr("aca_os.llm_verbalization.urlopen", _urlopen)
    result = LLMVerbalizer(
        config=_config(provider="ollama", model="qwen3:8b")
    ).verbalize(_brief())

    assert result.accepted is False
    assert result.fallback_reason == "validation_failed"
    assert result.final_response == result.deterministic_response


def test_llm_verbalization_benchmark_is_complete_and_passes():
    suite = load_llm_verbalization_benchmark()
    result = run_llm_verbalization_benchmark()

    assert suite["scenario_count"] >= 12
    assert result["passed"] is True
    assert result["quality"]["runtime_fidelity_percentage"] == 100.0
    assert result["quality"]["hallucination_detection_percentage"] == 100.0
    assert result["quality"]["fallback_correct_percentage"] == 100.0
    report = render_llm_verbalization_benchmark_report(result)
    assert "# ACA LLM Verbalization Benchmark" in report
    assert "naturaliza_apertura_generica" in report


def test_provider_comparison_reuses_same_benchmark_without_live_calls():
    comparison = run_llm_verbalization_provider_comparison()

    assert comparison["scenario_count"] == load_llm_verbalization_benchmark()["scenario_count"]
    assert comparison["method"] == "fixed_candidate_provider_conformance"
    assert comparison["live_network_calls"] is False
    assert comparison["passed"] is True
    assert set(comparison["profiles"]) == {"openai", "ollama", "deterministic"}
    assert comparison["profiles"]["openai"]["quality"]["runtime_fidelity_percentage"] == 100.0
    assert comparison["profiles"]["ollama"]["quality"]["runtime_fidelity_percentage"] == 100.0
    assert comparison["profiles"]["deterministic"]["quality"]["fallback_count"] == comparison["scenario_count"]
    report = render_llm_verbalization_provider_comparison(comparison)
    assert "# ACA LLM Provider Comparison" in report
    assert "| ollama |" in report


def test_language_realization_benchmark_improves_form_without_changing_authority():
    suite = load_language_realization_benchmark()
    result = run_language_realization_benchmark()

    assert suite["scenario_count"] == 10
    assert result["passed"] is True
    assert result["mode"] == "controlled_candidate"
    assert result["quality"]["semantic_preservation_percentage"] == 100.0
    assert result["quality"]["repetition_reduction_percentage"] == 100.0
    assert result["quality"]["bureaucratic_language_reduction_percentage"] == 100.0
    assert result["quality"]["syntactic_variety_percentage"] == 100.0
    assert result["quality"]["naturalness_percentage"] == 100.0
    assert result["quality"]["validator_acceptance_percentage"] == 100.0
    assert result["quality"]["runtime_authority_preservation_percentage"] == 100.0
    report = render_language_realization_benchmark_report(result)
    assert "# ACA Language Realization Benchmark" in report
    assert "realiza_prioridad_sin_repeticion" in report
