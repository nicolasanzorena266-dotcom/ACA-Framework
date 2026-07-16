from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import socket
from threading import Lock
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import ConversationState
from zero_cost.execution_plan import ExecutionPlan


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_LLM_TIMEOUT_SECONDS = 60.0
DEFAULT_OLLAMA_KEEP_ALIVE = "5m"
SUPPORTED_VALIDATION_MODES = {"standard", "strict"}
_CACHE_LIMIT = 128
_WARMUP_LOCK = Lock()
_WARMUP_EVENTS: dict[tuple[str, str, str], dict[str, Any]] = {}


@dataclass(frozen=True)
class LLMVerbalizationConfig:
    enabled: bool = False
    provider: str = "openai"
    model: str = ""
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS
    temperature: float | None = 0.2
    max_tokens: int = 300
    validation_mode: str = "strict"
    language: str = "es-AR"
    tone: str = "calm, direct and helpful"
    style: str = "natural customer-service conversation"
    api_key: str = field(default="", repr=False)
    base_url: str = DEFAULT_OPENAI_BASE_URL
    ollama_host: str = DEFAULT_OLLAMA_HOST
    ollama_keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE
    ollama_warmup_on_start: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMVerbalizationConfig":
        source = dict(os.environ if env is None else env)
        validation_mode = str(source.get("LLM_VALIDATION_MODE") or "strict").strip().lower()
        if validation_mode not in SUPPORTED_VALIDATION_MODES:
            validation_mode = "strict"
        provider = str(source.get("LLM_PROVIDER") or "openai").strip().lower()
        model = str(source.get("LLM_MODEL") or "").strip()
        if provider == "ollama":
            model = str(source.get("OLLAMA_MODEL") or model or DEFAULT_OLLAMA_MODEL).strip()
        temperature_text = str(source.get("LLM_TEMPERATURE") or "0.2").strip().lower()
        temperature = None if temperature_text in {"", "none", "null"} else _as_float(temperature_text, 0.2)
        return cls(
            enabled=_as_bool(source.get("LLM_ENABLED")),
            provider=provider,
            model=model,
            timeout_seconds=max(
                _as_float(source.get("LLM_TIMEOUT"), DEFAULT_LLM_TIMEOUT_SECONDS),
                0.1,
            ),
            temperature=temperature,
            max_tokens=max(_as_int(source.get("LLM_MAX_TOKENS"), 300), 1),
            validation_mode=validation_mode,
            language=str(source.get("LLM_LANGUAGE") or "es-AR").strip(),
            tone=str(source.get("LLM_TONE") or "calm, direct and helpful").strip(),
            style=str(source.get("LLM_STYLE") or "natural customer-service conversation").strip(),
            api_key=str(source.get("OPENAI_API_KEY") or "").strip(),
            base_url=str(source.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL).strip().rstrip("/"),
            ollama_host=_normalize_ollama_host(
                str(source.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).strip()
            ),
            ollama_keep_alive=(
                str(source.get("OLLAMA_KEEP_ALIVE") or DEFAULT_OLLAMA_KEEP_ALIVE).strip()
                or DEFAULT_OLLAMA_KEEP_ALIVE
            ),
            ollama_warmup_on_start=_as_bool(source.get("OLLAMA_WARMUP_ON_START")),
        )

    def unavailable_reason(self) -> str | None:
        if not self.enabled:
            return "llm_disabled"
        if not self.provider:
            return "missing_provider"
        if not self.model:
            return "missing_model"
        if self.provider == "openai" and not self.api_key:
            return "missing_api_key"
        if self.provider == "ollama" and not _valid_http_url(self.ollama_host):
            return "invalid_ollama_host"
        return None

    def observable(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "validation_mode": self.validation_mode,
            "language": self.language,
            "tone": self.tone,
            "style": self.style,
            "ollama_host": self.ollama_host if self.provider == "ollama" else None,
            "ollama_keep_alive": self.ollama_keep_alive if self.provider == "ollama" else None,
            "ollama_warmup_on_start": self.ollama_warmup_on_start,
        }


@dataclass(frozen=True)
class VerbalizationBrief:
    """Minimal read-only projection of already-authorized response content."""

    deterministic_response: str
    user_message: str
    selected_operation: Mapping[str, Any] = field(default_factory=dict)
    candidate_work: Mapping[str, Any] = field(default_factory=dict)
    case_state: Mapping[str, Any] = field(default_factory=dict)
    confirmed_facts: Mapping[str, Any] = field(default_factory=dict)
    pending_information: tuple[Mapping[str, Any], ...] = ()
    response_directives: Mapping[str, Any] = field(default_factory=dict)
    policy: Mapping[str, Any] = field(default_factory=dict)
    governance: Mapping[str, Any] = field(default_factory=dict)
    executed_tools: tuple[Mapping[str, Any], ...] = ()
    language: str = "es-AR"
    tone: str = "calm, direct and helpful"
    style: str = "natural customer-service conversation"
    authority_mode: str = "legacy_source"
    conversation_objective: Mapping[str, Any] = field(default_factory=dict)
    semantic_context: Mapping[str, Any] = field(default_factory=dict)
    conversation_context: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_runtime(
        cls,
        *,
        deterministic_response: str,
        state: CognitiveState,
        event: Event,
        execution_plan: ExecutionPlan,
        conversation_state: ConversationState | None,
        config: LLMVerbalizationConfig,
        authority_mode: str = "legacy_source",
        conversation_objective: Mapping[str, Any] | None = None,
        semantic_context: Mapping[str, Any] | None = None,
        conversation_context: Mapping[str, Any] | None = None,
    ) -> "VerbalizationBrief":
        facts = state.facts if isinstance(state.facts, Mapping) else {}
        response_plan = _trace_payload(facts.get("conversation_response_plan"), "plan")
        information_gain = _trace_payload(facts.get("conversation_information_gain_plan"), "plan")
        selected_question = _mapping(information_gain.get("selected_question"))
        if not selected_question:
            selected_question = _selected_question_from_response_plan(response_plan)

        candidate_work, case_state = _official_operational_projection(facts)
        governance = _official_governance_projection(facts)
        objective = _mapping(conversation_objective)
        objective_missing = tuple(
            {"slot": str(item)}
            for item in objective.get("missing_information") or []
            if str(item).strip()
        )
        return cls(
            deterministic_response=str(deterministic_response or "").strip(),
            user_message=str(event.payload or "").strip(),
            selected_operation={
                "flow": execution_plan.flow,
                "action": execution_plan.source_action,
                "program": execution_plan.kernel_program,
            },
            candidate_work=candidate_work,
            case_state=case_state,
            confirmed_facts=_confirmed_facts(conversation_state),
            pending_information=(
                objective_missing
                if authority_mode == "conversation_objective"
                else tuple(
                    item
                    for item in (
                        _pending_question_summary(selected_question),
                        *_required_information_summaries(response_plan),
                    )
                    if item
                )
            ),
            response_directives=(
                {}
                if authority_mode == "conversation_objective"
                else _response_directives(response_plan)
            ),
            policy=_policy_summary(state.policy_result),
            governance=governance,
            executed_tools=tuple(_executed_tool_summaries(state)),
            language=config.language,
            tone=config.tone,
            style=config.style,
            authority_mode=authority_mode,
            conversation_objective=objective,
            semantic_context=_mapping(semantic_context),
            conversation_context=_mapping(conversation_context),
        )

    def prompt_payload(self) -> dict[str, Any]:
        if self.authority_mode == "conversation_objective":
            next_step = _mapping(self.conversation_objective.get("next_step"))
            question_count = int(
                next_step.get("question_budget")
                if next_step.get("question_budget") is not None
                else (1 if next_step.get("action") == "request_information" else 0)
            )
            return {
                "content_authority": "conversation_objective",
                "conversation_objective": deepcopy(dict(self.conversation_objective)),
                "semantic_context": deepcopy(dict(self.semantic_context)),
                "conversation_context": deepcopy(dict(self.conversation_context)),
                "output_constraints": {
                    "question_count": question_count,
                    "maximum_sentences": 3,
                    "must_not_select_new_action": True,
                    "must_not_invent_information": True,
                },
                "selected_operation": deepcopy(dict(self.selected_operation)),
                "candidate_work": deepcopy(dict(self.candidate_work)),
                "case_state": deepcopy(dict(self.case_state)),
                "confirmed_facts": deepcopy(dict(self.confirmed_facts)),
                "pending_information": [deepcopy(dict(item)) for item in self.pending_information],
                "policy_constraints": deepcopy(dict(self.policy)),
                "governance_constraints": deepcopy(dict(self.governance)),
                "executed_tools": [deepcopy(dict(item)) for item in self.executed_tools],
                "language": self.language,
                "tone": self.tone,
                "style": self.style,
            }
        return {
            "source_response": self.deterministic_response,
            "output_constraints": {
                "question_count": self.deterministic_response.count("?"),
                "maximum_sentences": max(
                    1,
                    min(2, sum(self.deterministic_response.count(mark) for mark in ".?!")),
                ),
                "source_is_content_authority": True,
            },
            "selected_operation": deepcopy(dict(self.selected_operation)),
            "candidate_work": deepcopy(dict(self.candidate_work)),
            "case_state": deepcopy(dict(self.case_state)),
            "confirmed_facts": deepcopy(dict(self.confirmed_facts)),
            "pending_information": [deepcopy(dict(item)) for item in self.pending_information],
            "response_directives": deepcopy(dict(self.response_directives)),
            "policy_constraints": deepcopy(dict(self.policy)),
            "governance_constraints": deepcopy(dict(self.governance)),
            "executed_tools": [deepcopy(dict(item)) for item in self.executed_tools],
            "language": self.language,
            "tone": self.tone,
            "style": self.style,
        }

    def fingerprint(self) -> str:
        encoded = json.dumps(
            {
                "prompt": self.prompt_payload(),
                "user_message_cache_scope": self.user_message,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LLMProviderRequest:
    model: str
    instructions: str
    input_text: str
    timeout_seconds: float
    temperature: float | None
    max_tokens: int


@dataclass(frozen=True)
class LLMProviderResponse:
    text: str
    provider: str
    model: str
    request_id: str | None = None


class LLMVerbalizationProvider(Protocol):
    provider_name: str

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        ...


class LLMProviderError(RuntimeError):
    fallback_reason = "provider_error"


class LLMProviderTimeout(LLMProviderError):
    fallback_reason = "provider_timeout"


class LLMProviderUnavailable(LLMProviderError):
    fallback_reason = "provider_unavailable"


class LLMProviderModelNotFound(LLMProviderError):
    fallback_reason = "model_not_found"


class OllamaUnavailable(LLMProviderUnavailable):
    fallback_reason = "ollama_unavailable"


class OllamaModelNotFound(LLMProviderModelNotFound):
    fallback_reason = "ollama_model_not_found"


class OpenAIResponsesAdapter:
    """Provider adapter for OpenAI's Responses API using the standard library."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, base_url: str = DEFAULT_OPENAI_BASE_URL) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "instructions": request.instructions,
            "input": request.input_text,
            "max_output_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        http_request = Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                request_id = response.headers.get("x-request-id")
        except (TimeoutError, socket.timeout) as exc:
            raise LLMProviderTimeout("OpenAI request timed out") from exc
        except HTTPError as exc:
            raise LLMProviderError(f"OpenAI request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMProviderTimeout("OpenAI request timed out") from exc
            raise LLMProviderError("OpenAI network request failed") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMProviderError("OpenAI returned an invalid response") from exc

        text = _openai_output_text(data)
        if not text:
            raise LLMProviderError("OpenAI returned no output text")
        return LLMProviderResponse(
            text=text,
            provider=self.provider_name,
            model=str(data.get("model") or request.model),
            request_id=request_id or _optional_text(data.get("id")),
        )


class OllamaAdapter:
    """Local provider adapter for Ollama's native HTTP API."""

    provider_name = "ollama"

    def __init__(
        self,
        *,
        host: str = DEFAULT_OLLAMA_HOST,
        keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE,
    ) -> None:
        self.host = _normalize_ollama_host(host)
        self.keep_alive = str(keep_alive or DEFAULT_OLLAMA_KEEP_ALIVE).strip()

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        models = self._available_models(request.timeout_seconds)
        if not _ollama_model_available(request.model, models):
            raise OllamaModelNotFound(f"Ollama model is not available: {request.model}")

        options: dict[str, Any] = {"num_predict": request.max_tokens}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        payload = {
            "model": request.model,
            "system": request.instructions,
            "prompt": request.input_text,
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "options": options,
        }
        data, _ = self._request_json(
            Request(
                f"{self.host}/api/generate",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout_seconds=request.timeout_seconds,
        )
        text = str(data.get("response") or "").strip()
        if not text:
            raise LLMProviderError("Ollama returned no response text")
        if data.get("done") is False:
            raise LLMProviderError("Ollama returned an incomplete non-streaming response")
        return LLMProviderResponse(
            text=text,
            provider=self.provider_name,
            model=str(data.get("model") or request.model),
            request_id=_optional_text(data.get("created_at")),
        )

    def warmup(self, *, model: str, timeout_seconds: float) -> dict[str, Any]:
        payload = {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        data, _ = self._request_json(
            Request(
                f"{self.host}/api/generate",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout_seconds=timeout_seconds,
        )
        if data.get("done") is False:
            raise LLMProviderError("Ollama warmup returned an incomplete response")
        return {
            "model": str(data.get("model") or model),
            "model_loaded": True,
            "done_reason": _optional_text(data.get("done_reason")),
            "total_duration_ns": data.get("total_duration"),
            "load_duration_ns": data.get("load_duration"),
        }

    def _available_models(self, timeout_seconds: float) -> tuple[str, ...]:
        data, _ = self._request_json(
            Request(f"{self.host}/api/tags", method="GET"),
            timeout_seconds=timeout_seconds,
        )
        models: list[str] = []
        for item in data.get("models") or []:
            mapped = _mapping(item)
            for key in ("name", "model"):
                value = str(mapped.get(key) or "").strip()
                if value and value not in models:
                    models.append(value)
        return tuple(models)

    def _request_json(self, request: Request, *, timeout_seconds: float) -> tuple[dict[str, Any], str | None]:
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                request_id = response.headers.get("x-request-id")
        except (TimeoutError, socket.timeout) as exc:
            raise LLMProviderTimeout("Ollama request timed out") from exc
        except HTTPError as exc:
            error_text = _http_error_text(exc)
            if exc.code == 404 and "model" in normalize_text(error_text):
                raise OllamaModelNotFound(error_text or "Ollama model not found") from exc
            raise LLMProviderError(f"Ollama request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMProviderTimeout("Ollama request timed out") from exc
            raise OllamaUnavailable("Ollama is not available") from exc
        except OSError as exc:
            raise OllamaUnavailable("Ollama is not available") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMProviderError("Ollama returned an invalid response") from exc
        if not isinstance(data, Mapping):
            raise LLMProviderError("Ollama returned an invalid response object")
        return dict(data), request_id


ProviderBuilder = Callable[[LLMVerbalizationConfig], LLMVerbalizationProvider | None]


class LLMProviderFactory:
    """Resolves replaceable provider adapters without exposing them to Runtime."""

    def __init__(self, builders: Mapping[str, ProviderBuilder] | None = None) -> None:
        self._builders: dict[str, ProviderBuilder] = dict(builders or {})

    @classmethod
    def default(cls) -> "LLMProviderFactory":
        factory = cls()
        factory.register(
            "openai",
            lambda config: OpenAIResponsesAdapter(
                api_key=config.api_key,
                base_url=config.base_url,
            )
            if config.api_key
            else None,
        )
        factory.register(
            "ollama",
            lambda config: OllamaAdapter(
                host=config.ollama_host,
                keep_alive=config.ollama_keep_alive,
            ),
        )
        return factory

    def register(self, name: str, builder: ProviderBuilder) -> None:
        normalized = str(name or "").strip().lower()
        if not normalized:
            raise ValueError("Provider name is required")
        self._builders[normalized] = builder

    def create(self, config: LLMVerbalizationConfig) -> LLMVerbalizationProvider | None:
        builder = self._builders.get(config.provider)
        return builder(config) if builder is not None else None

    def supported_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))


@dataclass(frozen=True)
class VerbalizationValidation:
    accepted: bool
    mode: str
    checks: tuple[Mapping[str, Any], ...]
    rejection_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "mode": self.mode,
            "checks": [dict(check) for check in self.checks],
            "rejection_reasons": list(self.rejection_reasons),
        }


class DeterministicVerbalizationValidator:
    """Rejects observable authority changes without performing new reasoning."""

    def validate(
        self,
        *,
        candidate: str,
        brief: VerbalizationBrief,
        mode: str,
    ) -> VerbalizationValidation:
        source = brief.deterministic_response.strip()
        candidate = str(candidate or "").strip()
        grounding = _grounding_text(brief)
        checks: list[dict[str, Any]] = []

        checks.append(_check("non_empty", bool(candidate)))
        checks.append(_check("bounded_length", bool(candidate) and len(candidate) <= max(800, len(source) * 4)))
        checks.append(_check("cognitive_opacity", not _contains_internal_language(candidate)))
        checks.append(_check("numeric_grounding", not _novel_numeric_claims(candidate, grounding)))
        checks.append(_check("factual_grounding", not _invented_factual_claim(candidate, grounding)))
        checks.append(_check("operational_grounding", not _novel_operational_claims(candidate, grounding)))
        checks.append(_check("execution_grounding", not _invented_execution_claim(candidate, source, brief.executed_tools)))
        checks.append(_check("permission_grounding", not _invented_permission_claim(candidate, grounding)))
        checks.append(_check("question_budget", _question_budget_preserved(candidate, source, brief)))
        if mode == "strict":
            checks.append(_check("selected_question_preserved", _selected_question_preserved(candidate, source, brief)))
            checks.append(_check("authority_projection_read_only", True))

        reasons = tuple(str(check["name"]) for check in checks if not check["passed"])
        return VerbalizationValidation(
            accepted=not reasons,
            mode=mode,
            checks=tuple(checks),
            rejection_reasons=reasons,
        )


@dataclass(frozen=True)
class LLMVerbalizationResult:
    deterministic_response: str
    verbalized_response: str | None
    final_response: str
    provider_called: bool
    accepted: bool
    fallback_reason: str | None
    provider: str
    model: str
    validation: VerbalizationValidation
    latency_ms: float
    request_id: str | None = None
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "llm_verbalization_result.v1",
            "deterministic_response": self.deterministic_response,
            "verbalized_response": self.verbalized_response,
            "validation": self.validation.to_dict(),
            "response_sent": self.final_response,
            "provider_called": self.provider_called,
            "accepted": self.accepted,
            "fallback_reason": self.fallback_reason,
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
            "cache_hit": self.cache_hit,
            "latency_ms": self.latency_ms,
        }


class LLMVerbalizer:
    """Optional natural-language realization behind ACA's output boundary."""

    def __init__(
        self,
        *,
        config: LLMVerbalizationConfig | None = None,
        provider: LLMVerbalizationProvider | None = None,
        provider_factory: LLMProviderFactory | None = None,
        validator: DeterministicVerbalizationValidator | None = None,
    ) -> None:
        self.config = config or LLMVerbalizationConfig.from_env()
        self.provider_factory = provider_factory or LLMProviderFactory.default()
        self.provider = provider if provider is not None else self.provider_factory.create(self.config)
        self.validator = validator or DeterministicVerbalizationValidator()
        self._cache: OrderedDict[str, LLMVerbalizationResult] = OrderedDict()
        self._cache_lock = Lock()

    def verbalize(self, brief: VerbalizationBrief) -> LLMVerbalizationResult:
        started = perf_counter()
        fingerprint = brief.fingerprint()
        cached = self._cached(fingerprint)
        if cached is not None:
            return _with_cache_hit(cached)

        unavailable = self.config.unavailable_reason()
        if unavailable:
            result = self._fallback(brief, reason=unavailable, started=started)
            self._remember(fingerprint, result)
            return result
        if self.provider is None:
            reason = (
                "unsupported_provider"
                if self.config.provider not in self.provider_factory.supported_providers()
                else "provider_unavailable"
            )
            result = self._fallback(brief, reason=reason, started=started)
            self._remember(fingerprint, result)
            return result

        request = LLMProviderRequest(
            model=self.config.model,
            instructions=_provider_instructions(brief.authority_mode),
            input_text=json.dumps(brief.prompt_payload(), ensure_ascii=False, sort_keys=True),
            timeout_seconds=self.config.timeout_seconds,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        try:
            provider_response = self.provider.generate(request)
        except LLMProviderError as exc:
            result = self._fallback(
                brief,
                reason=exc.fallback_reason,
                started=started,
                provider_called=True,
            )
        except Exception:
            result = self._fallback(
                brief,
                reason="provider_error",
                started=started,
                provider_called=True,
            )
        else:
            candidate = provider_response.text.strip()
            validation = self.validator.validate(
                candidate=candidate,
                brief=brief,
                mode=self.config.validation_mode,
            )
            accepted = validation.accepted
            result = LLMVerbalizationResult(
                deterministic_response=brief.deterministic_response,
                verbalized_response=candidate,
                final_response=candidate if accepted else brief.deterministic_response,
                provider_called=True,
                accepted=accepted,
                fallback_reason=None if accepted else "validation_failed",
                provider=provider_response.provider,
                model=provider_response.model,
                validation=validation,
                latency_ms=_elapsed_ms(started),
                request_id=provider_response.request_id,
            )
        self._remember(fingerprint, result)
        return result

    def _fallback(
        self,
        brief: VerbalizationBrief,
        *,
        reason: str,
        started: float,
        provider_called: bool = False,
    ) -> LLMVerbalizationResult:
        validation = VerbalizationValidation(
            accepted=False,
            mode=self.config.validation_mode,
            checks=(),
            rejection_reasons=(reason,),
        )
        return LLMVerbalizationResult(
            deterministic_response=brief.deterministic_response,
            verbalized_response=None,
            final_response=brief.deterministic_response,
            provider_called=provider_called,
            accepted=False,
            fallback_reason=reason,
            provider=self.config.provider,
            model=self.config.model,
            validation=validation,
            latency_ms=_elapsed_ms(started),
        )

    def _cached(self, fingerprint: str) -> LLMVerbalizationResult | None:
        with self._cache_lock:
            result = self._cache.get(fingerprint)
            if result is not None:
                self._cache.move_to_end(fingerprint)
            return result

    def _remember(self, fingerprint: str, result: LLMVerbalizationResult) -> None:
        with self._cache_lock:
            self._cache[fingerprint] = result
            self._cache.move_to_end(fingerprint)
            while len(self._cache) > _CACHE_LIMIT:
                self._cache.popitem(last=False)


def build_default_llm_verbalizer(env: Mapping[str, str] | None = None) -> LLMVerbalizer:
    config = LLMVerbalizationConfig.from_env(env)
    verbalizer = LLMVerbalizer(config=config)
    if config.ollama_warmup_on_start:
        warmup_default_llm_provider(config=config, provider=verbalizer.provider)
    return verbalizer


def warmup_default_llm_provider(
    env: Mapping[str, str] | None = None,
    *,
    config: LLMVerbalizationConfig | None = None,
    provider: LLMVerbalizationProvider | None = None,
    provider_factory: LLMProviderFactory | None = None,
) -> dict[str, Any]:
    effective = config or LLMVerbalizationConfig.from_env(env)
    event = {
        "contract": "llm_runtime_readiness_event.v1",
        "event_type": "llm_provider_warmup",
        "provider": effective.provider,
        "model": effective.model,
        "timeout_seconds": effective.timeout_seconds,
        "keep_alive": effective.ollama_keep_alive if effective.provider == "ollama" else None,
        "warmup_requested": effective.ollama_warmup_on_start,
        "warmup_executed": False,
        "duration_ms": 0.0,
        "model_loaded": False,
        "status": "skipped",
        "failure_reason": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if not effective.ollama_warmup_on_start:
        event["failure_reason"] = "warmup_disabled"
        return event
    unavailable = effective.unavailable_reason()
    if unavailable:
        event["failure_reason"] = unavailable
        return event
    if effective.provider != "ollama":
        event["failure_reason"] = "warmup_not_supported_for_provider"
        return event

    key = (effective.ollama_host, effective.model, effective.ollama_keep_alive)
    with _WARMUP_LOCK:
        previous = _WARMUP_EVENTS.get(key)
        if previous is not None:
            return deepcopy(previous)

        started = perf_counter()
        event["warmup_executed"] = True
        try:
            selected = provider
            if selected is None:
                selected = (provider_factory or LLMProviderFactory.default()).create(effective)
            warmup = getattr(selected, "warmup", None)
            if not callable(warmup):
                raise LLMProviderError("Ollama warmup provider is unavailable")
            result = warmup(
                model=effective.model,
                timeout_seconds=effective.timeout_seconds,
            )
        except LLMProviderError as exc:
            event["status"] = "failed"
            event["failure_reason"] = exc.fallback_reason
        except Exception:
            event["status"] = "failed"
            event["failure_reason"] = "provider_error"
        else:
            event["status"] = "success"
            event["model"] = str(result.get("model") or effective.model)
            event["model_loaded"] = bool(result.get("model_loaded"))
            event["ollama"] = dict(result)
        event["duration_ms"] = _elapsed_ms(started)
        _WARMUP_EVENTS[key] = deepcopy(event)
        return deepcopy(event)


def _provider_instructions(authority_mode: str = "legacy_source") -> str:
    if authority_mode == "conversation_objective":
        return (
            "You are ACA's only natural-language writer. ACA already understood the turn and chose "
            "the goal, missing information, next step, operation, constraints and safety boundaries. "
            "Express those structured decisions as a natural, warm, concise customer-service reply. "
            "Use semantic_context only as grounded evidence for what the user said; never reinterpret it "
            "into a different goal or operation. Follow conversation_objective exactly. You may vary "
            "wording, sentence order, empathy, greetings, transitions and closings. Never exceed "
            "output_constraints.question_count. When next_step.action is request_information, a question "
            "may request only the named missing_information. A converse step may use its question budget "
            "only for a natural invitation to continue. If question_count is zero, ask nothing. Never "
            "invent facts, statuses, numbers, permissions, promises, tools, tool results or completed "
            "actions. Never expose internal contract names, planning, policy, governance, slots or runtime "
            "mechanisms. Use voseo for es-AR. Return only the visible response without labels."
        )
    return (
        "You are ACA's language realizer. ACA already decided the content. Write a fresh, warm, "
        "natural version of source_response: preserve meaning, not wording. Do not copy a complete "
        "source clause when it can be expressed naturally in another way. Reorder, simplify, connect "
        "ideas and remove repetition. Replace bureaucratic phrases such as 'corresponde', 'respecto de' "
        "or 'primero necesitamos' with direct conversational language. Preserve every fact, number, "
        "uncertainty, action, restriction, outcome and selected question. Keep every explicit domain "
        "or case noun from source_response, such as denuncia, expediente, servicio, documentacion or "
        "derivacion; never replace it with an implicit reference or omit it. Never add knowledge, facts, "
        "promises, tools, actions, offers or questions, and never omit a required question. Realize only "
        "source_response. "
        "Obey output_constraints exactly, especially question_count and maximum_sentences. If "
        "question_count is 0, write no question mark and ask nothing. "
        "Other JSON fields only ground the meaning. Follow the requested regional language; use "
        "voseo for es-AR. Never mention internal systems or reasoning. Follow these examples. "
        "SOURCE: Que necesitas resolver primero? Asi puedo responder primero la preocupacion mas "
        "importante. OUTPUT: Hola. Que necesitas resolver? Empecemos por lo que mas te preocupa. "
        "SOURCE: Tenes toda la documentacion? OUTPUT: Antes de seguir, ya tenes toda la documentacion "
        "que te pidieron? SOURCE: Si ya paso una semana y la denuncia sigue en tramite, corresponde "
        "revisar la demora. Alguien te contacto? OUTPUT: Entiendo, como la denuncia sigue en tramite "
        "despues de una semana, conviene revisar que la esta demorando. Alguien llego a contactarte? "
        "SOURCE: El plazo habitual depende de la revision. Respecto de la denuncia, falta confirmar si "
        "enviaron las fotos. OUTPUT: El tiempo puede variar segun la revision. Sobre la denuncia, todavia "
        "falta confirmar si enviaron las fotos. SOURCE: Primero necesitamos revisar el estado del servicio. "
        "El servicio esta caido solo en tu domicilio? OUTPUT: Empecemos por revisar el servicio. El problema "
        "ocurre solamente en tu domicilio? SOURCE: No tengo acceso al expediente. OUTPUT: Desde aca no puedo "
        "consultar el expediente. Return only the visible response, without labels, in at most two short "
        "sentences."
    )


def _trace_payload(value: Any, payload_key: str) -> dict[str, Any]:
    mapped = _mapping(value)
    payload = mapped.get(payload_key)
    return deepcopy(dict(payload)) if isinstance(payload, Mapping) else deepcopy(mapped)


def _selected_question_from_response_plan(response_plan: Mapping[str, Any]) -> dict[str, Any]:
    information_gain = _mapping(response_plan.get("information_gain_plan"))
    return _mapping(information_gain.get("selected_question"))


def _pending_question_summary(question: Mapping[str, Any]) -> dict[str, Any]:
    if not question:
        return {}
    return {
        "slot": question.get("slot"),
        "question": question.get("question") or question.get("prompt"),
        "purpose": question.get("purpose") or question.get("reason"),
        "needed_for": question.get("needed_for"),
    }


def _required_information_summaries(response_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in response_plan.get("required_information") or []:
        mapped = _mapping(item)
        if mapped:
            summaries.append(
                {
                    "key": mapped.get("key") or mapped.get("slot"),
                    "reason": mapped.get("reason") or mapped.get("purpose"),
                }
            )
        elif item:
            summaries.append({"key": str(item)})
    return summaries


def _response_directives(response_plan: Mapping[str, Any]) -> dict[str, Any]:
    primary = _mapping(response_plan.get("primary_user_need"))
    concern = _mapping(response_plan.get("dominant_concern"))
    next_action = _mapping(response_plan.get("next_action"))
    return {
        "primary_need": primary.get("label") or primary.get("key"),
        "dominant_concern": concern.get("label") or concern.get("key"),
        "response_priority": list(response_plan.get("response_priority") or []),
        "next_action": {
            "type": next_action.get("type"),
            "label": next_action.get("label"),
        }
        if next_action
        else {},
    }


def _confirmed_facts(conversation_state: ConversationState | None) -> dict[str, Any]:
    if conversation_state is None:
        return {}
    projected: dict[str, Any] = {}
    for key, raw in (conversation_state.confirmed_facts or {}).items():
        if str(key) in {"last_event_type", "last_raw_payload"}:
            continue
        mapped = _mapping(raw)
        status = str(mapped.get("status") or "active") if mapped else "active"
        if status not in {"active", "answered", "confirmed"}:
            continue
        projected[str(key)] = deepcopy(mapped.get("value") if mapped and "value" in mapped else raw)
        if len(projected) >= 20:
            break
    return projected


def _policy_summary(policy: Mapping[str, Any] | None) -> dict[str, Any]:
    mapped = _mapping(policy)
    if not mapped:
        return {}
    return {
        "decision": mapped.get("decision"),
        "modifications": deepcopy(list(mapped.get("modifications") or [])),
        "interrupted": str(mapped.get("decision") or "").upper() == "ESCALATE",
    }


def _official_operational_projection(facts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    direct_candidate = _mapping(facts.get("candidate_work"))
    direct_case = _mapping(facts.get("case_state_projection"))
    if direct_candidate or direct_case:
        return _candidate_summary(direct_candidate), _case_state_summary(direct_case)

    observed = _mapping(facts.get("operational_work"))
    if not observed or observed.get("mode") == "shadow" or observed.get("authoritative") is not True:
        return {}, {}
    selected = _mapping(observed.get("selected_work"))
    return _candidate_summary(selected), _case_state_summary(_mapping(observed.get("case_state_projection")))


def _official_governance_projection(facts: Mapping[str, Any]) -> dict[str, Any]:
    governance = _mapping(facts.get("operational_governance"))
    if not governance:
        governance = _mapping(facts.get("operational_governance_assessment"))
    if not governance or governance.get("mode") == "shadow":
        return {}
    return {
        "execution_allowed": governance.get("execution_allowed"),
        "requires_confirmation": governance.get("requires_confirmation"),
        "requires_human_approval": governance.get("requires_human_approval"),
        "risk_level": governance.get("risk_level"),
        "missing_preconditions": deepcopy(list(governance.get("missing_preconditions") or [])),
    }


def _candidate_summary(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not candidate:
        return {}
    return {
        "operation": candidate.get("operation"),
        "category": candidate.get("category") or candidate.get("operational_category"),
        "expected_outcome": candidate.get("expected_outcome"),
        "status": candidate.get("status"),
    }


def _case_state_summary(case_state: Mapping[str, Any]) -> dict[str, Any]:
    if not case_state:
        return {}
    allowed = (
        "case_stage",
        "documentation",
        "current_owner",
        "blockers",
        "dependencies",
        "pending_actions",
        "completed_actions",
        "available_evidence",
        "next_expected_change",
    )
    return {key: deepcopy(case_state.get(key)) for key in allowed if key in case_state}


def _executed_tool_summaries(state: CognitiveState) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for outcome in state.facts.get("execution_step_outcomes") or []:
        result = _mapping(_mapping(outcome).get("result"))
        execution = _mapping(result.get("tool_execution"))
        if not execution:
            continue
        summaries.append(
            {
                "tool": execution.get("tool_name"),
                "action": execution.get("action"),
                "executed": bool(execution.get("executed")),
                "mode": execution.get("mode"),
                "reason": execution.get("reason"),
            }
        )
    return summaries


def _openai_output_text(data: Mapping[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in data.get("output") or []:
        mapped_item = _mapping(item)
        if mapped_item.get("type") != "message":
            continue
        for content in mapped_item.get("content") or []:
            mapped_content = _mapping(content)
            if mapped_content.get("type") in {"output_text", "text"} and mapped_content.get("text"):
                parts.append(str(mapped_content["text"]))
    return "\n".join(part.strip() for part in parts if part.strip()).strip()


def _normalize_ollama_host(host: str) -> str:
    normalized = str(host or "").strip().rstrip("/")
    if normalized.lower().endswith("/api"):
        normalized = normalized[:-4].rstrip("/")
    return normalized


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ollama_model_available(requested: str, available: Sequence[str]) -> bool:
    normalized_requested = str(requested or "").strip().lower()
    normalized_available = {str(item).strip().lower() for item in available}
    if normalized_requested in normalized_available:
        return True
    if ":" not in normalized_requested:
        return f"{normalized_requested}:latest" in normalized_available
    return False


def _http_error_text(error: HTTPError) -> str:
    try:
        raw = error.read().decode("utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, Mapping):
            return str(parsed.get("error") or parsed.get("message") or raw)
        return raw
    except Exception:
        return ""


def _grounding_text(brief: VerbalizationBrief) -> str:
    return normalize_text(
        " ".join(
            [
                brief.deterministic_response,
                brief.user_message,
                json.dumps(brief.prompt_payload(), ensure_ascii=False, default=str),
            ]
        )
    )


def _contains_internal_language(text: str) -> bool:
    normalized = normalize_text(text)
    patterns = (
        r"\bruntime\b",
        r"\bconversation state\b",
        r"\bestado conversacional\b",
        r"\bconversation plan\b",
        r"\bexecution plan\b",
        r"\bcandidate work\b",
        r"\bcase state\b",
        r"\binformation gain\b",
        r"\bslot(?:s)?\b",
        r"\bpolicy\b",
        r"\bgovernance\b",
        r"\bprompt\b",
        r"\bmodelo de lenguaje\b",
        r"\brazonamiento interno\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _novel_numeric_claims(candidate: str, grounding: str) -> list[str]:
    candidate_normalized = normalize_text(candidate)
    tokens = set(re.findall(r"(?<!\w)(?:\$\s*)?\d+(?:[.,]\d+)?(?:\s*%)?(?!\w)", candidate_normalized))
    number_words = {"dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce"}
    tokens.update(word for word in number_words if re.search(rf"\b{word}\b", candidate_normalized))
    return sorted(token for token in tokens if token not in grounding)


def _novel_operational_claims(candidate: str, grounding: str) -> list[str]:
    normalized = normalize_text(candidate)
    protected = {
        "ticket",
        "visita tecnica",
        "bonificacion",
        "reembolso",
        "cancelacion",
        "derivacion",
        "callback",
        "factura modificada",
        "documentacion asociada",
    }
    return sorted(term for term in protected if term in normalized and term not in grounding)


def _invented_factual_claim(candidate: str, grounding: str) -> bool:
    normalized = normalize_text(candidate)
    name_match = re.search(r"\b(?:tu nombre es|te llamas)\s+([a-z][a-z0-9_-]+)", normalized)
    if name_match and name_match.group(1) not in grounding:
        return True
    protected_statuses = {
        "aprobada",
        "aprobado",
        "autorizada",
        "autorizado",
        "cancelada",
        "cancelado",
        "cerrada",
        "cerrado",
        "pagada",
        "pagado",
        "rechazada",
        "rechazado",
        "resuelta",
        "resuelto",
    }
    return any(status in normalized and status not in grounding for status in protected_statuses)


def _invented_execution_claim(
    candidate: str,
    source: str,
    executed_tools: Sequence[Mapping[str, Any]],
) -> bool:
    normalized = normalize_text(candidate)
    source_normalized = normalize_text(source)
    claim_pattern = re.compile(
        r"\b(?:ya\s+)?(?:cree|creamos|registre|registramos|envie|enviamos|asocie|asociamos|"
        r"cancele|cancelamos|modifique|modificamos|aplique|aplicamos|agende|agendamos|"
        r"programe|programamos|derive|derivamos)\b"
    )
    if not claim_pattern.search(normalized):
        return False
    if claim_pattern.search(source_normalized):
        return False
    return not any(bool(item.get("executed")) for item in executed_tools)


def _invented_permission_claim(candidate: str, grounding: str) -> bool:
    normalized = normalize_text(candidate)
    patterns = (
        "esta autorizado",
        "fue autorizado",
        "tenes permiso",
        "esta aprobado",
        "fue aprobado",
        "cobertura confirmada",
    )
    return any(pattern in normalized and pattern not in grounding for pattern in patterns)


def _question_budget_preserved(candidate: str, source: str, brief: VerbalizationBrief) -> bool:
    candidate_count = candidate.count("?")
    source_count = source.count("?")
    selected = any(item.get("question") for item in brief.pending_information)
    allowed = source_count if source_count else (1 if selected else 0)
    if candidate_count > allowed:
        return False
    if source_count and candidate_count == 0:
        return False
    return True


def _selected_question_preserved(candidate: str, source: str, brief: VerbalizationBrief) -> bool:
    selected = next((item for item in brief.pending_information if item.get("question")), None)
    if selected is None or "?" not in source:
        return True
    content = " ".join(
        str(selected.get(key) or "")
        for key in ("slot", "question", "purpose", "needed_for")
    )
    tokens = _meaningful_tokens(content)
    if not tokens:
        return True
    candidate_tokens = _meaningful_tokens(candidate)
    return bool(tokens & candidate_tokens)


def _meaningful_tokens(text: str) -> set[str]:
    stop = {
        "alguna",
        "alguno",
        "como",
        "cuando",
        "donde",
        "para",
        "poder",
        "porque",
        "pregunta",
        "recordas",
        "saber",
        "sobre",
        "tener",
        "tiene",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalize_text(text))
        if len(token) >= 5 and token not in stop
    }


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed)}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000.0, 3)


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _with_cache_hit(result: LLMVerbalizationResult) -> LLMVerbalizationResult:
    return LLMVerbalizationResult(
        deterministic_response=result.deterministic_response,
        verbalized_response=result.verbalized_response,
        final_response=result.final_response,
        provider_called=False,
        accepted=result.accepted,
        fallback_reason=result.fallback_reason,
        provider=result.provider,
        model=result.model,
        validation=result.validation,
        latency_ms=0.0,
        request_id=result.request_id,
        cache_hit=True,
    )
