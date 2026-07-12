from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, Mapping, Protocol

from aca_core import PluginRuntime
from aca_core.text import normalize_search_text


CLIENT_TECHNICAL_FORBIDDEN = (
    "no voy a inventar",
    "cambio de estrategia",
    "runtime",
    "policy",
    "fallback",
    "herramienta no disponible",
    "tool unavailable",
    "capability blocked",
    "en esta demo",
)

FALSE_OPERATIONAL_CLAIMS = (
    "estoy revisando tu denuncia",
    "veo tu expediente",
    "ya consulté el sistema",
    "te transfiero ahora",
    "acabo de cargar la documentación",
)

OBSERVABILITY_ACTIONS = {"show_process", "show_diagnostic"}

BILLING_DOMAIN_TERMS = (
    "factura",
    "facturación",
    "facturacion",
    "pago",
    "vencimiento",
    "importe",
    "monto",
    "cobro",
    "deuda",
)

INSURANCE_DOMAIN_TERMS = (
    "siniestro",
    "denuncia",
    "choque",
    "colisión",
    "colision",
    "cristal",
    "vidrio",
    "parabrisas",
    "robo",
    "accidente",
    "franquicia",
)

REPETITION_MARKERS = (
    "ya te dije",
    "ya te dijee",
    "ya me dijiste",
    "ya lo dijiste",
    "ya lo dije",
    "ya dije",
    "me estás repitiendo",
    "me estas repitiendo",
    "otra vez",
    "bue",
)

FRUSTRATION_MARKERS = (
    "bue",
    "no tiene sentido",
    "no entiendo lo que",
    "me estás mareando",
    "me estas mareando",
    "no me ayuda",
    "seguís repitiendo",
    "seguis repitiendo",
)

CAPABILITY_QUESTION_MARKERS = (
    "podés hacer algo más",
    "podes hacer algo mas",
    "qué podés hacer",
    "que podes hacer",
    "qué más podés",
    "que mas podes",
    "algo mas",
    "algo más",
)

HUMAN_REQUEST_MARKERS = (
    "quiero hablar con alguien",
    "hablar con alguien",
    "hablar con una persona",
    "quiero hablar con una persona",
    "representante",
    "supervisor",
    "deriv",
)

GENERIC_SERVICE_TERMS = (
    "baja",
    "dar de baja",
    "cancelación",
    "cancelacion",
    "cancelar",
)

INSURANCE_GLASS_TERMS = (
    "cristal",
    "vidrio",
    "parabrisas",
)

INSURANCE_ACCIDENT_TERMS = (
    "choque",
    "colision",
    "accidente",
)

INSURANCE_CLAIM_TERMS = (
    "denuncia",
    "siniestro",
    "robo",
    "franquicia",
    "poliza",
)

VEHICLE_TERMS = (
    "auto",
    "vehiculo",
    "coche",
)

REPAIR_TERMS = (
    "reparar",
    "reparacion",
    "arreglar",
    "arreglo",
    "taller",
    "presupuesto",
)

BAJA_REJECTION_MARKERS = (
    "nunca dije baja",
    "no dije baja",
    "no es baja",
    "no es una baja",
    "no pedi baja",
    "no pedi una baja",
    "no quiero baja",
    "no quiero dar de baja",
)

_LAYER_CACHE: Dict[str, "PublicConversationProductLayer"] = {}


@dataclass
class ConversationProductMemory:
    active_plugin_id: str | None = None
    active_capability: str | None = None
    claim_type: str | None = None
    domain: str | None = None
    billing_issue: str | None = None
    issue_focus: str | None = None
    expected_amount: str | None = None
    received_amount: str | None = None
    explicit_amounts: list[str] = field(default_factory=list)
    last_user_message: str | None = None
    last_response: str | None = None
    last_prompt_kind: str | None = None
    next_expected_user_input: str | None = None
    frustration_signals: int = 0
    handoff_requested: bool = False
    generic_topic: str | None = None
    dialogue_act: str | None = None
    current_goal: str | None = None
    next_action: str | None = None
    user_has_evidence: bool = False
    user_completed_review: bool = False
    last_options: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    completed_actions: list[str] = field(default_factory=list)
    response_signatures: list[str] = field(default_factory=list)
    turns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_plugin_id": self.active_plugin_id,
            "active_capability": self.active_capability,
            "claim_type": self.claim_type,
            "domain": self.domain,
            "billing_issue": self.billing_issue,
            "issue_focus": self.issue_focus,
            "expected_amount": self.expected_amount,
            "received_amount": self.received_amount,
            "explicit_amounts": list(self.explicit_amounts),
            "last_user_message": self.last_user_message,
            "last_response": self.last_response,
            "last_prompt_kind": self.last_prompt_kind,
            "next_expected_user_input": self.next_expected_user_input,
            "frustration_signals": self.frustration_signals,
            "handoff_requested": self.handoff_requested,
            "generic_topic": self.generic_topic,
            "dialogue_act": self.dialogue_act,
            "current_goal": self.current_goal,
            "next_action": self.next_action,
            "user_has_evidence": self.user_has_evidence,
            "user_completed_review": self.user_completed_review,
            "last_options": list(self.last_options),
            "suggested_actions": list(self.suggested_actions),
            "completed_actions": list(self.completed_actions),
            "response_signatures": list(self.response_signatures),
            "turns": self.turns,
        }


@dataclass(frozen=True)
class CognitiveTurnInput:
    message: str
    conversation_id: str
    conversation_mode: str
    memory: Mapping[str, Any]
    capabilities: tuple[str, ...]
    limits: tuple[str, ...]


@dataclass(frozen=True)
class CognitiveTurnOutput:
    domain: str | None
    topic: str | None
    dialogue_act: str
    facts: Mapping[str, Any]
    goal: str | None
    next_action: str
    response_strategy: str
    visible_response: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "topic": self.topic,
            "dialogue_act": self.dialogue_act,
            "facts": dict(self.facts),
            "goal": self.goal,
            "next_action": self.next_action,
            "response_strategy": self.response_strategy,
            "visible_response": self.visible_response,
        }


class DialogueController(Protocol):
    def decide(self, turn: CognitiveTurnInput) -> CognitiveTurnOutput:
        ...


class DeterministicDialogueController:
    """Offline bridge that returns the same structured shape expected from an LLM controller.

    It deliberately works at dialogue-act level rather than keyword-to-response level so
    RC5 can stop expanding one-off public conversation rules while preserving zero-cost tests.
    """

    def decide(self, turn: CognitiveTurnInput) -> CognitiveTurnOutput:
        text = normalize_search_text(turn.message)
        memory = turn.memory
        domain = _infer_domain_from_text_or_memory(text, memory)
        topic = _infer_topic_from_text_or_memory(text, memory)
        dialogue_act = _detect_dialogue_act(text=text, memory=memory)
        facts = _controller_facts(memory)
        goal = _infer_goal(domain=domain, topic=topic, memory=memory)
        next_action = _infer_next_action(dialogue_act=dialogue_act, domain=domain, topic=topic, memory=memory)
        strategy = _response_strategy_for(dialogue_act=dialogue_act, memory=memory)
        return CognitiveTurnOutput(
            domain=domain,
            topic=topic,
            dialogue_act=dialogue_act,
            facts=facts,
            goal=goal,
            next_action=next_action,
            response_strategy=strategy,
        )


@dataclass
class PublicConversationProductLayer:
    runtime: PluginRuntime
    conversation_memory: Dict[str, ConversationProductMemory] = field(default_factory=dict)
    dialogue_controller: DialogueController = field(default_factory=DeterministicDialogueController)

    @classmethod
    def from_path(cls, root: str | Path = "plugins") -> "PublicConversationProductLayer":
        return cls(runtime=PluginRuntime.from_path(root))

    def contract(self) -> Dict[str, Any]:
        actions: list[Dict[str, Any]] = []
        for plugin in self.runtime.plugin_registry.all():
            actions.extend(self._actions_for_plugin(plugin.domain_id))
        return {
            "contract": "public_conversation_product_layer.v1",
            "principle": "hooks propose; runtime applies; trace records",
            "conversation_modes": ["client_support", "developer_observation"],
            "public_actions": actions,
            "technical_language_blocked": list(CLIENT_TECHNICAL_FORBIDDEN),
            "false_claims_blocked": list(FALSE_OPERATIONAL_CLAIMS),
            "dialogue_controller": {
                "contract": "cognitive_turn_controller.v1",
                "mode": "deterministic_offline_bridge",
                "llm_ready": True,
                "output_shape": ["domain", "topic", "dialogue_act", "facts", "goal", "next_action", "response_strategy", "visible_response"],
            },
            "acceptance": {
                "observability_actions_do_not_write_visible_chat": True,
                "enabled_buttons_execute_real_actions": True,
                "client_support_blocks_internal_language": True,
            },
        }

    def run(
        self,
        *,
        message: str = "",
        conversation_id: str = "public-conversation",
        conversation_mode: str = "client_support",
        public_action_id: str | None = None,
    ) -> Dict[str, Any]:
        memory = self._memory_for(conversation_id)
        action_plugin_id: str | None = None
        action: Dict[str, Any] | None = None
        requested_capability: str | None = None
        if public_action_id:
            action_plugin_id, action = self._find_action(public_action_id, preferred_plugin_id=memory.active_plugin_id)
            requested_capability = action["capability"] if action else memory.active_capability
            if action and not action.get("enabled", True):
                return self._disabled_action_response(
                    action=action,
                    conversation_id=conversation_id,
                    conversation_mode=conversation_mode,
                    memory=memory,
                )
        if requested_capability is None:
            requested_capability = self._requested_capability_from_message(message=message, memory=memory)

        result = self.runtime.process(
            message,
            conversation_id=conversation_id,
            requested_capability=requested_capability,
            public_action_id=public_action_id,
            conversation_mode=conversation_mode,
        )
        result_dict = result.to_dict()
        active_plugin = result.route.selected_plugin_id or action_plugin_id or memory.active_plugin_id
        active_capability = result.route.selected_capability or requested_capability or memory.active_capability
        self._update_memory(
            memory=memory,
            message=message,
            plugin_id=active_plugin,
            capability=active_capability,
            action_id=public_action_id,
        )
        cognitive_turn = self._decide_cognitive_turn(
            message=message,
            conversation_id=conversation_id,
            conversation_mode=conversation_mode,
            memory=memory,
        )
        self._apply_cognitive_turn(memory=memory, turn=cognitive_turn)
        response = self._project_response(message=message, result=result_dict, action=action, memory=memory, cognitive_turn=cognitive_turn)
        response = supervise_visible_response(response=response, memory=memory)
        response = apply_exposure_filter(response, conversation_mode=conversation_mode)
        response = apply_capability_claim_filter(response)
        memory.last_response = response
        return {
            "contract": "public_conversation_product_layer.run.v1",
            "conversation_id": conversation_id,
            "request_id": result.request_id,
            "conversation_mode": conversation_mode,
            "input_type": "action" if public_action_id else "message",
            "public_action_id": public_action_id,
            "active_plugin_id": active_plugin,
            "active_capability": active_capability,
            "response": response,
            "chat_visible": public_action_id not in OBSERVABILITY_ACTIONS,
            "public_actions": self._actions_for_plugin(active_plugin),
            "public_trace": build_public_trace(result_dict),
            "diagnostic_view": build_diagnostic_view(result_dict, memory=memory),
            "developer_trace": result.trace,
            "hook_execution": dict(result.hook_execution),
            "conversation_memory": memory.to_dict(),
            "cognitive_turn": cognitive_turn.to_dict(),
        }

    def reset(self, conversation_id: str) -> Dict[str, Any]:
        self.conversation_memory.pop(conversation_id, None)
        return {"contract": "public_conversation_product_layer.reset.v1", "conversation_id": conversation_id, "status": "reset"}

    def _memory_for(self, conversation_id: str) -> ConversationProductMemory:
        return self.conversation_memory.setdefault(conversation_id, ConversationProductMemory())

    def _disabled_action_response(
        self,
        *,
        action: Mapping[str, Any],
        conversation_id: str,
        conversation_mode: str,
        memory: ConversationProductMemory,
    ) -> Dict[str, Any]:
        response = apply_exposure_filter(
            "Esa consulta no está conectada acá. Puedo ayudarte a preparar un resumen claro para continuar la gestión con una persona.",
            conversation_mode=conversation_mode,
        )
        request_id = f"disabled-{conversation_id}-{action['id']}"
        return {
            "contract": "public_conversation_product_layer.run.v1",
            "conversation_id": conversation_id,
            "request_id": request_id,
            "conversation_mode": conversation_mode,
            "input_type": "action",
            "public_action_id": action["id"],
            "active_plugin_id": memory.active_plugin_id,
            "active_capability": action["capability"],
            "response": apply_capability_claim_filter(response),
            "chat_visible": False,
            "public_actions": self._actions_for_plugin(memory.active_plugin_id) or self.contract()["public_actions"],
            "public_trace": {
                "trace_type": "public_trace.v1",
                "conversation_id": conversation_id,
                "request_id": request_id,
                "steps": ["Identifiqué la acción", "Validé que no está activa", "Preparé una alternativa segura"],
            },
            "diagnostic_view": {"status": "action_disabled", "capability": action["capability"], "disabled_reason": action.get("disabled_reason")},
            "developer_trace": {
                "active_plugin_id": memory.active_plugin_id,
                "active_capability": action["capability"],
                "events": [],
                "disabled_reason": action.get("disabled_reason"),
            },
            "hook_execution": {"semantic": False, "policy": False, "planner": False},
            "conversation_memory": memory.to_dict(),
        }


    def _decide_cognitive_turn(
        self,
        *,
        message: str,
        conversation_id: str,
        conversation_mode: str,
        memory: ConversationProductMemory,
    ) -> CognitiveTurnOutput:
        capabilities = tuple(self.runtime.capability_registry.capabilities())
        turn = CognitiveTurnInput(
            message=message,
            conversation_id=conversation_id,
            conversation_mode=conversation_mode,
            memory=memory.to_dict(),
            capabilities=capabilities,
            limits=(
                "no real billing system access",
                "no real human transfer",
                "no false operational claims",
            ),
        )
        return self.dialogue_controller.decide(turn)

    def _apply_cognitive_turn(self, *, memory: ConversationProductMemory, turn: CognitiveTurnOutput) -> None:
        memory.dialogue_act = turn.dialogue_act
        memory.current_goal = turn.goal
        memory.next_action = turn.next_action
        if turn.domain:
            memory.domain = turn.domain
        if turn.topic == "baja":
            memory.generic_topic = "baja"
        if turn.next_action == "offer_claim_draft" and "armar_reclamo" not in memory.suggested_actions:
            memory.suggested_actions.append("armar_reclamo")
        if turn.next_action == "prepare_handoff_summary" and "preparar_resumen" not in memory.suggested_actions:
            memory.suggested_actions.append("preparar_resumen")

    def _find_action(self, action_id: str, preferred_plugin_id: str | None = None) -> tuple[str | None, Dict[str, Any] | None]:
        plugins = self.runtime.plugin_registry.all()
        if preferred_plugin_id:
            plugins = sorted(plugins, key=lambda plugin: plugin.domain_id != preferred_plugin_id)
        for plugin in plugins:
            for action in plugin.manifest.public_actions:
                if action.id == action_id:
                    return plugin.domain_id, action.to_dict()
        return None, None

    def _actions_for_plugin(self, plugin_id: str | None) -> list[Dict[str, Any]]:
        if not plugin_id:
            return []
        plugin = self.runtime.plugin_registry.get(plugin_id)
        if plugin is None:
            return []
        return [action.to_dict() for action in plugin.manifest.public_actions]

    def _requested_capability_from_message(self, *, message: str, memory: ConversationProductMemory) -> str | None:
        text = normalize_search_text(message)
        insurance_capability = _insurance_capability_from_text(text)
        if insurance_capability:
            return insurance_capability
        if _is_billing_message(text) or _is_billing_context_continuation(text, memory):
            return "generic.open_chat"
        if _is_generic_service_message(text) or _is_generic_service_context_continuation(text, memory):
            return "generic.open_chat"
        if memory.claim_type and (_is_repetition_marker(text) or _should_continue_previous_capability(message)):
            return memory.active_capability
        if any(marker in text for marker in HUMAN_REQUEST_MARKERS):
            if memory.domain == "billing" or memory.generic_topic:
                return "generic.open_chat"
            return "insurance.handoff.prepare" if memory.active_plugin_id in {None, "galicia.insurance"} or memory.claim_type else memory.active_capability
        if any(marker in text for marker in ("cristal", "vidrio", "parabrisas")):
            return "insurance.glass"
        if any(marker in text for marker in ("choque", "colisión", "colision", "accidente")):
            return "insurance.accident"
        if any(marker in text for marker in ("denuncia", "siniestro", "robo", "franquicia")):
            return "insurance.claims"
        if memory.active_capability and _should_continue_previous_capability(message):
            return memory.active_capability
        return None

    def _update_memory(
        self,
        *,
        memory: ConversationProductMemory,
        message: str,
        plugin_id: str | None,
        capability: str | None,
        action_id: str | None,
    ) -> None:
        text = normalize_search_text(message)
        amount_text = message
        insurance_capability = _insurance_capability_from_text(text)
        memory.turns += 1
        memory.last_user_message = message
        if _rejects_baja_topic(text):
            _clear_generic_service_memory(memory)
        if _is_repetition_marker(text) or _is_frustration_marker(text):
            memory.frustration_signals += 1
        if _is_evidence_confirmation(text):
            memory.user_has_evidence = True
        if _is_completed_review(text):
            memory.user_completed_review = True
            if "revisar_factura" not in memory.completed_actions:
                memory.completed_actions.append("revisar_factura")
        if plugin_id:
            memory.active_plugin_id = plugin_id
        if capability:
            memory.active_capability = capability

        if insurance_capability:
            _clear_generic_service_memory(memory)
            memory.billing_issue = None
            memory.issue_focus = None
            memory.last_options = []
            memory.next_expected_user_input = None
            memory.domain = "insurance"
            memory.active_plugin_id = "galicia.insurance"
            memory.active_capability = insurance_capability
            if insurance_capability == "insurance.glass":
                memory.claim_type = "cristales"
            elif memory.claim_type == "cristales":
                memory.claim_type = None
        elif _is_billing_message(text) or _is_billing_context_continuation(text, memory):
            memory.domain = "billing"
            memory.active_plugin_id = "generic.open_chat"
            memory.active_capability = "generic.open_chat"
        if not insurance_capability and (_is_generic_service_message(text) or _is_generic_service_context_continuation(text, memory)):
            memory.generic_topic = "baja" if _mentions_baja(text) or memory.generic_topic == "baja" else memory.generic_topic
            memory.domain = memory.domain or "service_request"
            memory.active_plugin_id = "generic.open_chat"
            memory.active_capability = "generic.open_chat"
            memory.next_expected_user_input = "service_request_scope"
        selected_option = _selected_billing_option(text)
        if selected_option and _billing_context_exists(memory):
            memory.issue_focus = selected_option
            if selected_option in {"reclamo", "reclamo_iniciado"}:
                memory.billing_issue = "reclamo_factura"
            memory.next_expected_user_input = "billing_" + selected_option
        if any(term in text for term in ("importe", "monto", "valor")) or _extract_amounts(amount_text):
            if memory.domain == "billing" or _is_billing_message(text):
                memory.issue_focus = "importe"
                memory.billing_issue = memory.billing_issue or "importe_incorrecto"
                memory.next_expected_user_input = "billing_amount_followup"
        if any(term in text for term in ("mayor", "distinto", "diferente", "más alto", "mas alto")) and (memory.domain == "billing" or _is_billing_message(text)):
            memory.billing_issue = "importe_mayor_al_esperado"
            memory.issue_focus = memory.issue_focus or "importe"

        amounts = _extract_amounts(amount_text)
        if amounts and (memory.domain == "billing" or _is_billing_message(text) or "me dijeron" in text):
            for amount in amounts:
                if amount not in memory.explicit_amounts:
                    memory.explicit_amounts.append(amount)
            if len(amounts) >= 2:
                memory.expected_amount = memory.expected_amount or amounts[0]
                memory.received_amount = memory.received_amount or amounts[1]
                memory.billing_issue = "importe_incorrecto"
                memory.issue_focus = "importe"
                memory.domain = "billing"
                memory.active_plugin_id = "generic.open_chat"
                memory.active_capability = "generic.open_chat"
            elif len(amounts) == 1 and memory.expected_amount is None:
                memory.expected_amount = amounts[0]

        if "cristal" in text or "vidrio" in text or capability == "insurance.glass":
            memory.claim_type = "cristales"
            memory.active_plugin_id = "galicia.insurance"
            memory.active_capability = "insurance.glass"
        if action_id == "prepare_handoff" or "persona" in text or "representante" in text:
            memory.handoff_requested = True

    def _project_response(self, *, message: str, result: Mapping[str, Any], action: Mapping[str, Any] | None, memory: ConversationProductMemory, cognitive_turn: CognitiveTurnOutput) -> str:
        route = result.get("route") or {}
        plugin_id = route.get("selected_plugin_id") or memory.active_plugin_id
        capability = route.get("selected_capability") or memory.active_capability
        text = normalize_search_text(message)
        plan = result.get("plan") or {}
        if action and action.get("id") == "show_process":
            return "Proceso listo en el panel derecho. La conversación principal queda intacta."
        if action and action.get("id") == "show_diagnostic":
            return "Diagnóstico listo en el panel derecho. No agregué mensajes al chat del cliente."
        if action and action.get("id") == "prepare_handoff":
            return _handoff_response(memory=memory)
        if plugin_id == "galicia.insurance" or capability in {"insurance.claims", "insurance.glass", "insurance.accident", "insurance.handoff.prepare"}:
            return _project_insurance_response(text=text, capability=str(capability or ""), plan=plan, memory=memory, cognitive_turn=cognitive_turn)
        return _project_generic_response(text=text, memory=memory, cognitive_turn=cognitive_turn)


def _contains_normalized_phrase(text: str, phrase: str) -> bool:
    normalized_text = normalize_search_text(text)
    normalized_phrase = normalize_search_text(phrase)
    if not normalized_text or not normalized_phrase:
        return False
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
            normalized_text,
        )
    )


def _contains_any_normalized_phrase(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_normalized_phrase(text, term) for term in terms)


def _is_billing_message(text: str) -> bool:
    return any(term in text for term in BILLING_DOMAIN_TERMS)


def _is_insurance_message(text: str) -> bool:
    return bool(_insurance_capability_from_text(text))


def _insurance_capability_from_text(text: str) -> str | None:
    if _contains_any_normalized_phrase(text, INSURANCE_GLASS_TERMS):
        return "insurance.glass"
    if _contains_any_normalized_phrase(text, INSURANCE_ACCIDENT_TERMS):
        return "insurance.accident"
    if _contains_any_normalized_phrase(text, INSURANCE_CLAIM_TERMS) or _mentions_vehicle_repair(text):
        return "insurance.claims"
    return None


def _insurance_topic_from_text(text: str) -> str | None:
    capability = _insurance_capability_from_text(text)
    if capability == "insurance.glass":
        return "cristales"
    if capability == "insurance.accident":
        return "siniestro"
    if capability == "insurance.claims":
        if _contains_normalized_phrase(text, "denuncia"):
            return "denuncia"
        return "siniestro"
    return None


def _mentions_vehicle_repair(text: str) -> bool:
    return _contains_any_normalized_phrase(text, VEHICLE_TERMS) and _contains_any_normalized_phrase(text, REPAIR_TERMS)


def _is_repetition_marker(text: str) -> bool:
    return any(marker in text for marker in REPETITION_MARKERS)


def _is_frustration_marker(text: str) -> bool:
    return any(marker in text for marker in FRUSTRATION_MARKERS)


def _is_capability_question(text: str) -> bool:
    return any(marker in text for marker in CAPABILITY_QUESTION_MARKERS)


def _is_human_request(text: str) -> bool:
    return any(marker in text for marker in HUMAN_REQUEST_MARKERS)


def _is_short_affirmation(text: str) -> bool:
    return normalize_search_text(text) in {"si", "dale", "ok", "okay"}


def _is_ping_after_silence(text: str) -> bool:
    return normalize_search_text(text) in {"hola", "estas", "seguis"}


def _is_evidence_confirmation(text: str) -> bool:
    stripped = normalize_search_text(text)
    return any(marker in stripped for marker in ("lo tengo", "tengo aca", "tengo acá", "lo tengo acá", "lo tengo aca"))


def _is_completed_review(text: str) -> bool:
    stripped = normalize_search_text(text)
    return any(marker in stripped for marker in ("ya lo revise", "ya lo revisé", "lo revise", "lo revisé", "ya revisé", "ya revise"))


def _mentions_baja(text: str) -> bool:
    if _rejects_baja_topic(text):
        return False
    return _contains_any_normalized_phrase(text, GENERIC_SERVICE_TERMS)


def _rejects_baja_topic(text: str) -> bool:
    return _contains_any_normalized_phrase(text, BAJA_REJECTION_MARKERS)


def _clear_generic_service_memory(memory: ConversationProductMemory) -> None:
    if memory.generic_topic == "baja":
        memory.generic_topic = None
    if memory.domain == "service_request":
        memory.domain = None
    if memory.next_expected_user_input == "service_request_scope":
        memory.next_expected_user_input = None


def _is_generic_service_message(text: str) -> bool:
    return _mentions_baja(text)


def _generic_service_context_exists(memory: ConversationProductMemory) -> bool:
    return bool(memory.generic_topic)


def _is_generic_service_context_continuation(text: str, memory: ConversationProductMemory) -> bool:
    if not _generic_service_context_exists(memory):
        return False
    stripped = normalize_search_text(text)
    return bool(
        _is_repetition_marker(stripped)
        or _is_human_request(stripped)
        or _is_capability_question(stripped)
        or _is_frustration_marker(stripped)
        or stripped in {"una baja", "baja", "estado", "reclamo", "iniciar", "ya la pedí", "ya la pedi"}
    )


def _selected_billing_option(text: str) -> str | None:
    stripped = normalize_search_text(text)
    if stripped in {"importe", "el importe", "monto", "el monto", "valor", "el valor"}:
        return "importe"
    if stripped in {"vencimiento", "el vencimiento", "fecha de vencimiento"}:
        return "vencimiento"
    if stripped in {"pago", "el pago", "cobro", "el cobro"}:
        return "pago"
    if stripped in {"reclamo", "un reclamo", "reclamo ya iniciado", "un reclamo ya iniciado", "reclamo iniciado"}:
        return "reclamo_iniciado" if "iniciado" in stripped else "reclamo"
    return None


def _extract_amounts(text: str) -> list[str]:
    matches = re.findall(r"\$\s*[0-9][0-9.,]*", text)
    return [re.sub(r"\s+", "", match) for match in matches]


def _billing_context_exists(memory: ConversationProductMemory) -> bool:
    return memory.domain == "billing" or memory.active_capability == "generic.open_chat" and bool(memory.billing_issue or memory.issue_focus or memory.expected_amount or memory.received_amount)


def _is_billing_context_continuation(text: str, memory: ConversationProductMemory) -> bool:
    if not _billing_context_exists(memory):
        return False
    stripped = normalize_search_text(text)
    return bool(
        _extract_amounts(text)
        or _is_repetition_marker(stripped)
        or _is_frustration_marker(stripped)
        or _is_capability_question(stripped)
        or _is_human_request(stripped)
        or _is_ping_after_silence(stripped)
        or _is_short_affirmation(stripped)
        or _is_evidence_confirmation(stripped)
        or _is_completed_review(stripped)
        or _selected_billing_option(stripped)
        or "me dijeron" in stripped
        or "me llegó" in stripped
        or "me llego" in stripped
    )


def _infer_domain_from_text_or_memory(text: str, memory: Mapping[str, Any]) -> str | None:
    if _insurance_capability_from_text(text):
        return "insurance"
    if _is_billing_message(text) or memory.get("domain") == "billing":
        return "billing"
    if _is_generic_service_message(text) or (memory.get("generic_topic") and not _rejects_baja_topic(text)):
        return "service_request"
    if _is_insurance_message(text) or memory.get("claim_type"):
        return "insurance"
    return memory.get("domain")


def _infer_topic_from_text_or_memory(text: str, memory: Mapping[str, Any]) -> str | None:
    selected = _selected_billing_option(text)
    if selected:
        return selected
    insurance_topic = _insurance_topic_from_text(text)
    if insurance_topic:
        return insurance_topic
    if "factura" in text or memory.get("domain") == "billing":
        return "factura"
    if _mentions_baja(text) or (memory.get("generic_topic") == "baja" and not _rejects_baja_topic(text)):
        return "baja"
    if "cristal" in text or memory.get("claim_type") == "cristales":
        return "cristales"
    return memory.get("issue_focus") or memory.get("generic_topic") or memory.get("claim_type")


def _controller_facts(memory: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "domain": memory.get("domain"),
        "topic": memory.get("generic_topic") or memory.get("claim_type") or memory.get("issue_focus"),
        "expected_amount": memory.get("expected_amount"),
        "received_amount": memory.get("received_amount"),
        "issue_focus": memory.get("issue_focus"),
        "user_has_evidence": memory.get("user_has_evidence"),
        "user_completed_review": memory.get("user_completed_review"),
    }


def _detect_dialogue_act(*, text: str, memory: Mapping[str, Any]) -> str:
    if _is_human_request(text):
        return "user_requests_human"
    if _is_capability_question(text):
        return "user_requests_capabilities"
    if _is_ping_after_silence(text):
        return "user_pinged_after_silence"
    if _is_completed_review(text):
        return "user_completed_step"
    if _is_evidence_confirmation(text):
        return "user_confirmed_evidence"
    if _selected_billing_option(text):
        return "user_selected_option"
    if _is_repetition_marker(text):
        return "user_marks_repetition"
    if _is_frustration_marker(text):
        return "user_frustrated"
    if _is_short_affirmation(text):
        return "user_affirms"
    if _is_generic_service_message(text) or _is_billing_message(text) or _is_insurance_message(text):
        return "user_named_topic"
    return "user_message"


def _infer_goal(*, domain: str | None, topic: str | None, memory: Mapping[str, Any]) -> str | None:
    if domain == "billing":
        if topic in {"reclamo", "reclamo_iniciado"} or memory.get("billing_issue") == "reclamo_factura":
            return "ordenar seguimiento de reclamo de factura"
        return "preparar reclamo por factura"
    if topic == "baja":
        return "orientar trámite de baja sin consultar sistemas internos"
    if domain == "insurance":
        return "orientar trámite de siniestro"
    return None


def _infer_next_action(*, dialogue_act: str, domain: str | None, topic: str | None, memory: Mapping[str, Any]) -> str:
    if dialogue_act == "user_requests_human":
        return "prepare_handoff_summary"
    if dialogue_act == "user_requests_capabilities":
        return "explain_available_actions"
    if dialogue_act == "user_pinged_after_silence":
        return "repair_continuity"
    if dialogue_act in {"user_confirmed_evidence", "user_completed_step"}:
        return "offer_claim_draft" if domain == "billing" else "advance_next_step"
    if dialogue_act in {"user_frustrated", "user_marks_repetition"} and int(memory.get("frustration_signals") or 0) >= 2:
        return "escalate_to_concrete_action"
    if dialogue_act == "user_selected_option":
        return "advance_selected_option"
    if topic == "baja":
        return "ask_service_request_scope"
    if domain == "billing":
        return "orient_billing"
    return "orient_next_step"


def _response_strategy_for(*, dialogue_act: str, memory: Mapping[str, Any]) -> str:
    if dialogue_act in {"user_frustrated", "user_marks_repetition"} and int(memory.get("frustration_signals") or 0) >= 2:
        return "stop_explaining_offer_action"
    if dialogue_act in {"user_confirmed_evidence", "user_completed_step", "user_selected_option", "user_requests_capabilities", "user_requests_human"}:
        return "advance_not_repeat"
    return "orient_once"


def _billing_amount_pair(memory: ConversationProductMemory) -> tuple[str | None, str | None]:
    expected = memory.expected_amount
    received = memory.received_amount
    if (expected is None or received is None) and len(memory.explicit_amounts) >= 2:
        expected = expected or memory.explicit_amounts[0]
        received = received or memory.explicit_amounts[1]
    return expected, received


def _record_signature(memory: ConversationProductMemory, response: str) -> None:
    signature = re.sub(r"\$[0-9][0-9.,]*", "$X", response.lower())
    signature = re.sub(r"\s+", " ", signature).strip()[:180]
    memory.response_signatures.append(signature)
    memory.response_signatures = memory.response_signatures[-3:]


def _project_billing_response(*, text: str, memory: ConversationProductMemory, cognitive_turn: CognitiveTurnOutput) -> str:
    expected, received = _billing_amount_pair(memory)
    dialogue_act = cognitive_turn.dialogue_act
    selected = _selected_billing_option(text) or memory.issue_focus

    if dialogue_act == "user_requests_capabilities":
        return "Puedo ayudarte de tres formas: armar el mensaje de reclamo, preparar un resumen para un representante o listar los datos que conviene adjuntar. No puedo consultar tu factura real desde acá."
    if dialogue_act == "user_pinged_after_silence":
        return "Estoy acá. Con lo que ya contaste, puedo seguir de forma concreta: armar el reclamo por la factura, preparar un resumen para derivarlo o ayudarte a ordenar la evidencia."
    if dialogue_act == "user_requests_human":
        return _handoff_response(memory=memory)
    if dialogue_act == "user_confirmed_evidence":
        if expected and received:
            return f"Perfecto. Si tenés acá la evidencia de {expected} y la factura llegó por {received}, el próximo paso ya no es revisar lo mismo: es armar el reclamo por diferencia de importe o preparar un resumen para que lo tome una persona."
        return "Perfecto. Si ya tenés la evidencia a mano, puedo ayudarte a convertir eso en un reclamo claro o en un resumen para derivarlo."
    if dialogue_act == "user_completed_step":
        if expected and received:
            return f"Bien. Si ya revisaste la factura y sigue sin explicación la diferencia entre {expected} y {received}, el siguiente paso es reclamar el cargo aplicado y adjuntar la evidencia del importe informado."
        return "Bien. Si ya lo revisaste y el problema sigue, no tiene sentido volver al mismo paso: avancemos con el reclamo o el resumen para derivación."
    if dialogue_act in {"user_frustrated", "user_marks_repetition"}:
        if memory.frustration_signals >= 2:
            if expected and received:
                return f"Sí, me quedé girando sobre el mismo punto. No repito lo mismo: ya tenemos el problema de factura por importe, {expected} informado contra {received} facturado. Lo útil ahora es armar el reclamo o preparar el resumen para una persona."
            return "Sí, me quedé girando sobre el mismo punto. No repito lo mismo: ya tenemos el tema de factura/importe; lo útil ahora es armar el reclamo o preparar un resumen para continuar con una persona."
        if expected and received:
            return f"Tenés razón, ya lo dijiste. El problema es la factura por diferencia de importe: {expected} informado contra {received} facturado. No sigo pidiéndote revisar lo mismo; avancemos con el reclamo."
        return "Tenés razón, ya lo dijiste. El tema es la factura. No repito el menú: avancemos con una acción concreta, como armar el reclamo o preparar un resumen."
    if dialogue_act == "user_selected_option":
        if selected == "importe" and expected and received:
            return f"Perfecto, entonces el foco es el importe: {expected} informado contra {received} facturado. El próximo paso es pedir revisión del cargo aplicado con la factura y la evidencia del importe informado."
        if selected == "importe":
            return "Perfecto, entonces el foco es el importe. Para avanzar, compará monto informado, monto facturado y período; después puedo ayudarte a redactar el reclamo."
        if selected == "reclamo":
            return "Perfecto, entonces el foco es el reclamo de factura. Puedo ayudarte a separar si querés iniciarlo desde cero o si ya existe uno para hacer seguimiento."
        if selected == "reclamo_iniciado":
            return "Perfecto, entonces el foco es un reclamo de factura ya iniciado. Puedo ayudarte a preparar un mensaje de seguimiento con número de reclamo, fecha de carga, motivo y respuesta esperada."
        if selected == "vencimiento":
            return "Perfecto, entonces el foco es el vencimiento. Puedo ayudarte a ordenar fecha de vencimiento, período facturado, posible recargo y qué pedir en el canal correspondiente."
        if selected == "pago":
            return "Perfecto, entonces el foco es el pago. Ordenemos fecha, medio de pago, comprobante y período facturado para pedir revisión sin mezclar temas."
    if expected and received:
        if _is_short_affirmation(text):
            return f"Bien. Entonces seguimos por el reclamo de importe: factura recibida por {received} contra un importe informado de {expected}. Puedo armarte el texto del reclamo o un resumen para derivarlo."
        return f"Entiendo. Entonces el reclamo es por diferencia de importe: te habían informado {expected} y llegó una factura de {received}. El próximo paso es revisar si corresponde a cargos acumulados, cambio de plan, deuda previa, error de facturación o falta de aplicación de una bonificación. Tené a mano la factura, el período facturado y el mensaje o comprobante donde te informaron {expected}."
    if memory.issue_focus == "importe" or "monto" in text or "importe" in text or "valor" in text:
        memory.last_options = ["importe", "vencimiento", "pago", "reclamo_iniciado"]
        return "Sobre la factura, el foco es el importe. Para ordenar el reclamo conviene comparar monto esperado contra monto cobrado, período facturado, cargos nuevos y si había una bonificación o acuerdo previo."
    if "vencimiento" in text:
        return "Sobre la factura, el punto es el vencimiento. Puedo ayudarte a ordenar qué dato necesitás revisar y qué información conviene tener a mano antes de continuar por el canal correspondiente."
    if "pago" in text or "cobro" in text:
        return "Sobre el pago de la factura, puedo ayudarte a ordenar la consulta de forma general: fecha de pago, medio utilizado, comprobante y período facturado. No tengo acceso operativo a un sistema de facturación desde acá."
    memory.last_options = ["importe", "vencimiento", "pago", "reclamo_iniciado"]
    return "Sobre la factura, puedo orientarte de forma general sin consultar un sistema de facturación. Para avanzar, decime si querés revisar importe, vencimiento, pago o un reclamo ya iniciado."


def _project_service_request_response(*, text: str, memory: ConversationProductMemory, cognitive_turn: CognitiveTurnOutput) -> str:
    dialogue_act = cognitive_turn.dialogue_act
    if dialogue_act == "user_requests_human":
        return "Sí. No puedo transferirte directamente desde acá, pero puedo dejarte armado un resumen: querés revisar una baja y necesitás hablar con una persona para continuar el trámite."
    if dialogue_act == "user_requests_capabilities":
        return "Puedo ayudarte a ordenar la baja, distinguir si querés iniciarla o consultar una ya pedida, armar un resumen para un representante y dejar listo el mensaje de reclamo si no se aplicó."
    if dialogue_act in {"user_frustrated", "user_marks_repetition"}:
        if memory.frustration_signals >= 2:
            return "Sí, me quedé pidiendo lo mismo. El tema ya está: querés revisar una baja. Ahora lo útil es definir si es una baja nueva, una baja ya solicitada o un reclamo porque no se aplicó."
        return "Tenés razón. El tema ya está: querés revisar una baja. No vuelvo a pedirlo; avancemos distinguiendo si es iniciar la baja, ver estado de una baja pedida o reclamar porque no se aplicó."
    if _mentions_baja(text) or memory.generic_topic == "baja":
        return "Entiendo: querés revisar una baja. Puedo ayudarte a ordenar el caso sin consultar sistemas internos. Para avanzar, necesito distinguir si querés iniciar una baja, consultar el estado de una baja ya pedida o reclamar porque la baja no se aplicó."
    return "Puedo ayudarte a ordenar el trámite y preparar el próximo paso sin fingir acceso a sistemas internos."


def _project_generic_response(*, text: str, memory: ConversationProductMemory, cognitive_turn: CognitiveTurnOutput) -> str:
    if _is_billing_message(text) or _is_billing_context_continuation(text, memory) or _billing_context_exists(memory):
        return _project_billing_response(text=text, memory=memory, cognitive_turn=cognitive_turn)
    if _is_generic_service_message(text) or _is_generic_service_context_continuation(text, memory) or memory.generic_topic:
        return _project_service_request_response(text=text, memory=memory, cognitive_turn=cognitive_turn)
    if cognitive_turn.dialogue_act == "user_requests_capabilities":
        return "Puedo ayudarte a ordenar el caso, armar un mensaje, preparar un resumen para una persona o listar qué datos conviene tener a mano. No puedo consultar sistemas reales desde acá."
    if cognitive_turn.dialogue_act == "user_requests_human":
        return _handoff_response(memory=memory)
    if _is_repetition_marker(text):
        return "Tenés razón, ya lo dijiste. No repito la misma respuesta: tomo el tema que veníamos trabajando y avanzo con una acción concreta."
    return "Te puedo orientar paso a paso. Nombrame el trámite o problema y te ayudo a ordenar el próximo movimiento."


def _should_continue_previous_capability(message: str) -> bool:
    text = normalize_search_text(message)
    return any(
        marker in text
        for marker in (
            "48",
            "ya te dije",
            "ya me dijiste",
            "ya dijiste",
            "documentación",
            "documentacion",
            "cliente",
            "te la comparto",
            "app",
            "denuncia",
            "respuesta",
        )
    )


def _project_insurance_response(*, text: str, capability: str, plan: Mapping[str, Any], memory: ConversationProductMemory, cognitive_turn: CognitiveTurnOutput) -> str:
    if _is_billing_message(text):
        return _project_generic_response(text=text, memory=memory, cognitive_turn=cognitive_turn)
    claim_type = memory.claim_type or ("cristales" if capability == "insurance.glass" else None)
    if cognitive_turn.dialogue_act == "user_requests_capabilities":
        return "Puedo orientarte con documentación, plazos generales, demora del trámite o preparar un resumen para una persona. No puedo consultar el estado real del siniestro desde acá."
    if cognitive_turn.dialogue_act == "user_pinged_after_silence":
        return "Estoy acá. Seguimos con el trámite de cristales: puedo revisar el próximo paso, preparar el resumen de demora o ayudarte a ordenar qué reclamar."
    if "persona" in text or "representante" in text or plan.get("next_action") == "prepare_handoff":
        return _handoff_response(memory=memory)
    if "48" in text and (claim_type == "cristales" or "cristal" in text):
        return "Si ya pasaron más de 48 horas hábiles desde la denuncia de cristales, el próximo paso es pedir revisión con el número de trámite y confirmar que las fotos/documentación estén cargadas en el canal oficial."
    if "te la comparto" in text or "documentación" in text or "documentacion" in text:
        return "Por acá no hace falta que me la compartas. Tenela lista y cargala o verificá que ya esté subida en el mismo canal donde iniciaste la denuncia."
    if _is_repetition_marker(text) or _is_frustration_marker(text):
        if memory.frustration_signals >= 2:
            return "Sí, me quedé girando sobre lo mismo. Ya tenemos cristales, denuncia cargada y demora; ahora corresponde preparar el resumen para revisión o derivación."
        return "Tenés razón. No repito la lista: en este punto ordenamos el reclamo y preparamos el resumen para que revisen la demora."
    if "actúes" in text or "actues" in text or "cliente" in text:
        if claim_type == "cristales":
            return "Entendido. Sigo como atención al cliente: tomo que el trámite es por cristales y que la denuncia ya fue cargada desde la app. Ahora revisamos el próximo paso sin volver al inicio."
        return "Entendido. Sigo como atención al cliente y te voy guiando con el trámite sin volver a explicar el sistema."
    if "cristal" in text or "vidrio" in text or claim_type == "cristales":
        return "Para cristales, lo importante es que la denuncia esté cargada, las fotos se vean claras y el trámite tenga una autorización o próximo paso. Si eso ya está y no hubo respuesta, corresponde pedir revisión."
    return "Te oriento con el trámite. Contame qué parte quedó trabada y avanzamos desde ahí."


def _handoff_response(*, memory: ConversationProductMemory) -> str:
    expected, received = _billing_amount_pair(memory)
    if memory.domain == "billing" and expected and received:
        return f"Te preparo un resumen: consulta por factura con diferencia de importe, {expected} informado contra {received} facturado. El cliente indica que cuenta con evidencia y solicita revisión del cargo aplicado."
    if memory.generic_topic == "baja":
        return "Te preparo un resumen: el cliente quiere revisar una baja y necesita continuar con una persona para confirmar estado, aplicación o reclamo del trámite."
    if memory.claim_type == "cristales":
        return "Te preparo un resumen: denuncia de cristales cargada desde la app, documentación/fotos disponibles y demora mayor a 48 horas hábiles. Con eso una persona puede continuar sin que repitas todo."
    return "Te preparo un resumen breve con el motivo de contacto, lo que ya contaste y el próximo paso esperado para que una persona continúe la gestión."


def supervise_visible_response(response: str, *, memory: ConversationProductMemory) -> str:
    clean = response.strip() or "Estoy acá. Puedo ayudarte a ordenar el próximo paso sin consultar sistemas reales desde acá."
    repeated = _response_repeats_recent_semantic_signature(clean, memory)
    if repeated and memory.frustration_signals:
        expected, received = _billing_amount_pair(memory)
        if memory.domain == "billing" and expected and received:
            clean = f"Para no girar sobre lo mismo: ya tenemos {expected} informado y {received} facturado. Lo útil ahora es armar el reclamo o preparar un resumen para derivarlo."
        elif memory.domain == "billing":
            clean = "Para no girar sobre lo mismo: el tema es la factura y el importe. Lo útil ahora es elegir una acción concreta: armar reclamo, preparar resumen o definir qué dato falta."
        elif memory.generic_topic == "baja":
            clean = "Para no girar sobre lo mismo: el tema es una baja. Lo útil ahora es definir si querés iniciar, consultar estado o reclamar que no se aplicó."
        elif memory.claim_type == "cristales":
            clean = "Para no girar sobre lo mismo: ya tenemos cristales y demora. Lo útil ahora es preparar el resumen para revisión."
        else:
            clean = "Para no girar sobre lo mismo, avancemos con una acción concreta: armar mensaje, preparar resumen o definir el próximo paso."
    _record_signature(memory, clean)
    return clean


def _response_repeats_recent_semantic_signature(response: str, memory: ConversationProductMemory) -> bool:
    signature = re.sub(r"\$[0-9][0-9.,]*", "$X", response.lower())
    signature = re.sub(r"\s+", " ", signature).strip()[:180]
    return signature in memory.response_signatures[-3:]


def apply_exposure_filter(response: str, *, conversation_mode: str) -> str:
    if conversation_mode != "client_support":
        return response
    filtered = response
    replacements = {
        "no voy a inventar": "voy a ser claro con lo que se puede hacer desde acá",
        "cambio de estrategia": "lo reformulo",
        "runtime": "proceso",
        "policy": "regla",
        "fallback": "alternativa",
        "herramienta no disponible": "esa consulta no está conectada acá",
        "tool unavailable": "esa consulta no está conectada acá",
        "capability blocked": "esa acción no está habilitada acá",
        "en esta demo": "acá",
    }
    for forbidden, replacement in replacements.items():
        filtered = filtered.replace(forbidden, replacement).replace(forbidden.capitalize(), replacement.capitalize())
    return filtered


def apply_capability_claim_filter(response: str) -> str:
    filtered = response
    replacements = {
        "estoy revisando tu denuncia": "puedo ayudarte a ordenar la información de tu denuncia",
        "veo tu expediente": "con los datos del trámite",
        "ya consulté el sistema": "con la información que me indiques",
        "te transfiero ahora": "puedo preparar un resumen para derivación",
        "acabo de cargar la documentación": "la documentación debe cargarse por el canal correspondiente",
    }
    for claim, replacement in replacements.items():
        filtered = filtered.replace(claim, replacement).replace(claim.capitalize(), replacement.capitalize())
    return filtered


def build_public_trace(result: Mapping[str, Any]) -> Dict[str, Any]:
    route = result.get("route") or {}
    return {
        "trace_type": "public_trace.v1",
        "conversation_id": ((result.get("state") or {}).get("conversation_id")),
        "request_id": result.get("request_id"),
        "plugin_id": route.get("selected_plugin_id"),
        "capability": route.get("selected_capability"),
        "steps": [
            "Entendí el tema principal",
            "Validé qué acción se puede mostrar",
            "Preparé una respuesta para el cliente",
        ],
    }


def build_diagnostic_view(result: Mapping[str, Any], *, memory: ConversationProductMemory | None = None) -> Dict[str, Any]:
    route = result.get("route") or {}
    return {
        "trace_type": "diagnostic_view.v1",
        "selected_plugin_id": route.get("selected_plugin_id"),
        "selected_capability": route.get("selected_capability"),
        "hook_execution": dict(result.get("hook_execution") or {}),
        "plan": dict(result.get("plan") or {}),
        "policy_decision": dict(result.get("policy_decision") or {}),
        "conversation_memory": memory.to_dict() if memory else {},
    }


def build_public_conversation_product_layer(root: str | Path = "plugins") -> Dict[str, Any]:
    return get_public_conversation_product_layer(root).contract()


def get_public_conversation_product_layer(root: str | Path = "plugins") -> PublicConversationProductLayer:
    key = str(root)
    if key not in _LAYER_CACHE:
        _LAYER_CACHE[key] = PublicConversationProductLayer.from_path(root)
    return _LAYER_CACHE[key]


def run_public_conversation_product_layer(
    *,
    message: str = "",
    conversation_id: str = "public-conversation",
    conversation_mode: str = "client_support",
    public_action_id: str | None = None,
    root: str | Path = "plugins",
) -> Dict[str, Any]:
    layer = get_public_conversation_product_layer(root)
    if public_action_id == "reset_conversation":
        return layer.reset(conversation_id)
    return layer.run(
        message=message,
        conversation_id=conversation_id,
        conversation_mode=conversation_mode,
        public_action_id=public_action_id,
    )
