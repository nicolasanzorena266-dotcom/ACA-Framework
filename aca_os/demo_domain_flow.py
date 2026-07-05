from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.execution_trace import sanitize
from aca_os.representative_answer_composer import RepresentativeAnswerComposer
from aca_os.public_conversation_state import (
    get_public_conversation_state,
    update_public_conversation_state,
)
DEMO_DOMAIN_RUNTIME_FLOW_CONTRACT = "demo_domain_runtime_flow.v1"
DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT = "demo_domain_runtime_flow.scenario.v1"
DEFAULT_DOMAIN_PACK_ROOT = "examples/domain_packs"
DEFAULT_DOMAIN_PACK = "example.customer_support"


@dataclass(frozen=True)
class DemoDomainRuntimeScenario:
    """Human-testable scenario for running a loaded Domain Pack through Runtime APIs."""

    domain_pack_root: str = DEFAULT_DOMAIN_PACK_ROOT
    default_pack: str = DEFAULT_DOMAIN_PACK
    sample_messages: tuple[str, ...] = (
        "Check ticket 12345 status",
        "What documents are missing for case 9988?",
        "This is urgent, escalate ticket 7711 because the client is blocked",
        "Where is the bottleneck in onboarding process?",
    )
    endpoints: tuple[Mapping[str, str], ...] = (
        {"method": "GET", "path": "/demo/domain-flow"},
        {"method": "POST", "path": "/demo/domain-flow"},
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT,
            "domain_pack_root": self.domain_pack_root,
            "default_pack": self.default_pack,
            "sample_messages": list(self.sample_messages),
            "endpoints": [dict(endpoint) for endpoint in self.endpoints],
            "metadata": {
                "purpose": "local_human_runtime_demo",
                "business_logic": "domain_pack_data_plus_runtime_api",
                "domain_logic_embedded_in_interface": False,
            },
        }


@dataclass(frozen=True)
class DemoDomainRuntimeFlowResult:
    conversation_id: str
    message: str
    pack: Mapping[str, Any]
    intent: Mapping[str, Any]
    flow: Mapping[str, Any]
    entities: Mapping[str, Any]
    response: str
    runtime_execution: Mapping[str, Any]
    binding: Mapping[str, Any] = field(default_factory=dict)
    conversation_state: Mapping[str, Any] = field(default_factory=dict)
    next_step: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        trace = self.runtime_execution.get("execution_trace", {})
        operations = trace.get("operations", []) if isinstance(trace, Mapping) else []
        return sanitize(
            {
                "contract": DEMO_DOMAIN_RUNTIME_FLOW_CONTRACT,
                "conversation_id": self.conversation_id,
                "message": self.message,
                "domain": {
                    "pack": self.pack.get("name"),
                    "domain": self.pack.get("domain"),
                    "version": self.pack.get("version"),
                },
                "matched_intent": self.intent,
                "selected_flow": self.flow,
                "entities": dict(self.entities),
                "response": self.response,
                "trace_summary": {
                    "trace_id": trace.get("trace_id") if isinstance(trace, Mapping) else None,
                    "operation_count": len(operations),
                    "runtime_id": trace.get("runtime_id") if isinstance(trace, Mapping) else None,
                },
                "runtime_execution": self.runtime_execution,
                "binding": self.binding,
                "conversation_state": dict(self.conversation_state),
                "next_step": self.next_step,
                "metadata": {
                    "source": "runtime_api",
                    "domain_pack_used": True,
                    "llm_used": False,
                    "deterministic": True,
                },
            }
        )


class DemoDomainRuntimeFlowRunner:
    """Run a deterministic human demo against Runtime-loaded Domain Packs.

    This is deliberately outside the Runtime core. It demonstrates how interfaces
    can call Runtime APIs, load a Domain Pack root and execute a domain-shaped
    flow without importing pack code or hardcoding business behavior into REST or
    Studio adapters.
    """

    def __init__(self, api: Any | None = None) -> None:
        if api is None:
            from aca_os.runtime_api_endpoints import RuntimeEndpointAPI

            api = RuntimeEndpointAPI()
        self.api = api

    def scenario_contract(self) -> Dict[str, Any]:
        return DemoDomainRuntimeScenario().to_dict()

    def run(
        self,
        *,
        message: str,
        conversation_id: str = "demo-domain-flow",
        root: str | Path = DEFAULT_DOMAIN_PACK_ROOT,
        pack_name: str | None = None,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not message:
            raise ValueError("message is required.")
        pack_snapshot = self.api.domain_packs(root=root, memory_path=memory_path)
        packs = [pack for pack in pack_snapshot.get("packs", []) if isinstance(pack, Mapping)]
        if not packs:
            raise ValueError(f"No Domain Packs loaded from root: {root}")

        state_before = get_public_conversation_state(conversation_id)
        pack = _select_pack(packs, pack_name=pack_name, message=message)
        intent = _match_intent(pack, message)
        flow = _match_flow(pack, intent)
        entities = _extract_entities(message=message, intent=intent, pack=pack, state=state_before)
        answer = RepresentativeAnswerComposer().compose(
            message=message,
            pack=pack,
            intent=intent,
            flow=flow,
            entities=entities,
            state=state_before,
        )
        state_after = update_public_conversation_state(
            state_before,
            message=message,
            pack=pack,
            intent=intent,
            entities=entities,
            answer_category=answer.category,
            answer_next_step=answer.next_step,
            answer_text=answer.text,
        )
        response = answer.text

        runtime_execution = self.api.process_event(
            event_type="demo_domain_flow",
            payload={
                "message": message,
                "domain_pack": pack.get("name"),
                "intent": intent.get("name"),
                "flow": flow.get("name"),
                "entities": entities,
            },
            metadata={
                "conversation_id": conversation_id,
                "demo": "domain_runtime_flow",
                "domain_pack_root": str(root),
            },
            memory_path=memory_path,
            include_trace=True,
            include_introspection=True,
            include_studio=True,
        )
        binding = self.api.studio_binding(root=root, memory_path=memory_path)
        return DemoDomainRuntimeFlowResult(
            conversation_id=conversation_id,
            message=message,
            pack=pack,
            intent=intent,
            flow=flow,
            entities=entities,
            response=response,
            runtime_execution=runtime_execution,
            binding=binding,
            conversation_state=state_after.to_dict(),
            next_step=answer.next_step,
        ).to_dict()


def _select_pack(packs: Iterable[Mapping[str, Any]], *, pack_name: str | None, message: str) -> Mapping[str, Any]:
    pack_list = list(packs)
    if pack_name:
        for pack in pack_list:
            if pack.get("name") == pack_name or pack.get("domain") == pack_name:
                return pack
        raise KeyError(f"Domain Pack not found in loaded demo root: {pack_name}")

    normalized = _norm(message)
    if any(word in normalized for word in ["process", "workflow", "metric", "kpi", "bottleneck", "operation"]):
        for pack in pack_list:
            if pack.get("name") == "example.operations_basic":
                return pack
    for pack in pack_list:
        if pack.get("name") == DEFAULT_DOMAIN_PACK:
            return pack
    return pack_list[0]


def _match_intent(pack: Mapping[str, Any], message: str) -> Mapping[str, Any]:
    intents = _asset_items(pack, "intents", "intents")
    normalized = _norm(message)
    scored: list[tuple[int, Mapping[str, Any]]] = []
    for intent in intents:
        score = 0
        for utterance in intent.get("utterances", []):
            words = [word for word in _norm(str(utterance)).split() if len(word) > 2]
            if _norm(str(utterance)) in normalized:
                score += 6
            score += sum(1 for word in words if word in normalized)
        name = str(intent.get("name", ""))
        if any(word in normalized for word in ["status", "estado", "ticket", "caso", "tramite", "trámite"]) and any(word in name for word in ["status", "case", "support"]):
            score += 4
        if any(word in normalized for word in ["document", "documentation", "missing", "send"]):
            if "documentation" in name or "missing" in name:
                score += 4
        if any(word in normalized for word in ["urgent", "escalate", "priority", "blocked"]):
            if "escalation" in name:
                score += 4
        if any(word in normalized for word in ["process", "workflow", "bottleneck"]):
            if "process" in name or "review" in name:
                score += 4
        if any(word in normalized for word in ["metric", "kpi", "performing"]):
            if "metric" in name:
                score += 4
        scored.append((score, intent))

    if not scored:
        raise ValueError(f"No intents asset found for pack: {pack.get('name')}")
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_intent = scored[0]
    if best_score <= 0:
        return {
            "name": "demo.fallback",
            "description": "Fallback demo intent when no Domain Pack utterance matches.",
            "required_entities": [],
            "default_flow": _default_flow_name(pack),
            "confidence": 0.0,
        }
    return {**dict(best_intent), "confidence": min(1.0, best_score / 10)}


def _match_flow(pack: Mapping[str, Any], intent: Mapping[str, Any]) -> Mapping[str, Any]:
    flows = _asset_items(pack, "flows", "flows")
    target = intent.get("default_flow") or _default_flow_name(pack)
    for flow in flows:
        if flow.get("name") == target:
            return dict(flow)
    if flows:
        return dict(flows[0])
    raise ValueError(f"No flows asset found for pack: {pack.get('name')}")


def _extract_entities(*, message: str, intent: Mapping[str, Any], pack: Mapping[str, Any], state: Any | None = None) -> Dict[str, Any]:
    normalized = _norm(message)
    entities: Dict[str, Any] = {}
    match = re.search(r"\b(?:case|ticket|request)?\s*#?\s*(\d{3,})\b", normalized)
    if match:
        entities["case_id"] = match.group(1)
    elif state is not None and getattr(state, "active_case_id", None):
        entities["case_id"] = state.active_case_id
    if "process_name" in intent.get("required_entities", []) or pack.get("domain") == "operations.basic":
        process = re.search(r"(?:process|workflow)\s+([a-z0-9 _-]{3,40})", normalized)
        if process:
            entities["process_name"] = process.group(1).strip(" ?.,")
        elif "bottleneck" in normalized:
            entities["process_name"] = "demo_process"
    if "metric_name" in intent.get("required_entities", []) or "metric" in normalized or "kpi" in normalized:
        metric = re.search(r"(?:metric|kpi)\s+([a-z0-9 _-]{2,40})", normalized)
        entities["metric_name"] = metric.group(1).strip(" ?.,") if metric else "demo_metric"
    if "reason" in intent.get("required_entities", []) and any(word in normalized for word in ["urgent", "blocked", "priority"]):
        entities["reason"] = "urgent_or_blocked_request"

    missing = [entity for entity in intent.get("required_entities", []) if entity not in entities]
    if missing:
        entities["missing_required"] = missing
    return entities


def _render_response(*, message: str, pack: Mapping[str, Any], intent: Mapping[str, Any], flow: Mapping[str, Any], entities: Mapping[str, Any]) -> str:
    return RepresentativeAnswerComposer().compose(
        message=message,
        pack=pack,
        intent=intent,
        flow=flow,
        entities=entities,
    ).text



def _is_identity_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in [
        "sos un bot",
        "eres un bot",
        "sos bot",
        "que sos",
        "quien sos",
        "que eres",
        "quien eres",
    ])


def _is_capability_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in [
        "no tenes ia",
        "no tienes ia",
        "tenes ia",
        "tienes ia",
        "solo podes responder",
        "solo puedes responder",
        "podes responder",
        "puedes responder",
        "inteligencia artificial",
        "chatgpt",
    ])


def _is_confusion_question(normalized: str) -> bool:
    compact = normalized.strip().replace("¿", "").replace("?", "")
    return compact in {"eh", "ehh", "que", "cómo", "como", "no entiendo", "no entendi", "no entendí"}

def _asset_items(pack: Mapping[str, Any], asset_name: str, list_key: str) -> list[Mapping[str, Any]]:
    for asset in pack.get("assets", []):
        if isinstance(asset, Mapping) and asset.get("name") == asset_name:
            content = asset.get("content")
            if isinstance(content, Mapping):
                items = content.get(list_key, [])
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, Mapping)]
    return []


def _default_flow_name(pack: Mapping[str, Any]) -> str:
    flows = _asset_items(pack, "flows", "flows")
    return str(flows[0].get("name")) if flows else "demo.no_flow"


def _norm(value: str) -> str:
    return value.lower().strip()
