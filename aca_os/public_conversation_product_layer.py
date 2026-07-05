from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_core import PluginRuntime


CLIENT_TECHNICAL_FORBIDDEN = (
    "no voy a inventar",
    "cambio de estrategia",
    "runtime",
    "policy",
    "fallback",
    "herramienta no disponible",
    "tool unavailable",
    "capability blocked",
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
    "ya lo dije",
    "ya dije",
    "me estás repitiendo",
    "me estas repitiendo",
    "otra vez",
)

_LAYER_CACHE: Dict[str, "PublicConversationProductLayer"] = {}


@dataclass
class ConversationProductMemory:
    active_plugin_id: str | None = None
    active_capability: str | None = None
    claim_type: str | None = None
    last_response: str | None = None
    handoff_requested: bool = False
    turns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_plugin_id": self.active_plugin_id,
            "active_capability": self.active_capability,
            "claim_type": self.claim_type,
            "last_response": self.last_response,
            "handoff_requested": self.handoff_requested,
            "turns": self.turns,
        }


@dataclass
class PublicConversationProductLayer:
    runtime: PluginRuntime
    conversation_memory: Dict[str, ConversationProductMemory] = field(default_factory=dict)

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
        response = self._project_response(message=message, result=result_dict, action=action, memory=memory)
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
            "Esa consulta no está conectada en esta demo. Puedo ayudarte a preparar un resumen claro para continuar la gestión con una persona.",
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
        text = message.lower()
        if _is_billing_message(text):
            return "generic.open_chat"
        if any(marker in text for marker in ("persona", "representante", "deriv", "supervisor")):
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
        text = message.lower()
        memory.turns += 1
        if plugin_id:
            memory.active_plugin_id = plugin_id
        if capability:
            memory.active_capability = capability
        if _is_billing_message(text):
            memory.active_plugin_id = "generic.open_chat"
            memory.active_capability = "generic.open_chat"
        if "cristal" in text or "vidrio" in text or capability == "insurance.glass":
            memory.claim_type = "cristales"
            memory.active_plugin_id = "galicia.insurance"
            memory.active_capability = "insurance.glass"
        if action_id == "prepare_handoff" or "persona" in text or "representante" in text:
            memory.handoff_requested = True

    def _project_response(self, *, message: str, result: Mapping[str, Any], action: Mapping[str, Any] | None, memory: ConversationProductMemory) -> str:
        route = result.get("route") or {}
        plugin_id = route.get("selected_plugin_id") or memory.active_plugin_id
        capability = route.get("selected_capability") or memory.active_capability
        text = message.lower()
        plan = result.get("plan") or {}
        if action and action.get("id") == "show_process":
            return "Proceso listo en el panel derecho. La conversación principal queda intacta."
        if action and action.get("id") == "show_diagnostic":
            return "Diagnóstico listo en el panel derecho. No agregué mensajes al chat del cliente."
        if action and action.get("id") == "prepare_handoff":
            return _handoff_response(memory=memory)
        if plugin_id == "galicia.insurance" or capability in {"insurance.claims", "insurance.glass", "insurance.accident", "insurance.handoff.prepare"}:
            return _project_insurance_response(text=text, capability=str(capability or ""), plan=plan, memory=memory)
        return _project_generic_response(text=text, memory=memory)


def _is_billing_message(text: str) -> bool:
    return any(term in text for term in BILLING_DOMAIN_TERMS)


def _is_insurance_message(text: str) -> bool:
    return any(term in text for term in INSURANCE_DOMAIN_TERMS)


def _is_repetition_marker(text: str) -> bool:
    return any(marker in text for marker in REPETITION_MARKERS)


def _project_generic_response(*, text: str, memory: ConversationProductMemory) -> str:
    if _is_repetition_marker(text):
        if memory.active_capability == "generic.open_chat":
            return "Tenés razón, ya lo dijiste. No te vuelvo a pedir lo mismo: el tema es la factura. Para orientarte mejor necesito saber si querés revisar importe, vencimiento, pago o un reclamo ya iniciado."
        return "Tenés razón, ya lo dijiste. No repito la misma respuesta: ordenemos el punto concreto que querés resolver y avanzo sobre eso."
    if _is_billing_message(text):
        if "monto" in text or "importe" in text or "valor" in text:
            return "Sobre la factura, entiendo que el problema es que el importe llegó distinto al esperado. Puedo ayudarte a ordenar el reclamo: conviene identificar período facturado, monto esperado, monto cobrado y si ya hubo un reclamo previo."
        if "vencimiento" in text:
            return "Sobre la factura, el punto es el vencimiento. Puedo ayudarte a ordenar qué dato necesitás revisar y qué información conviene tener a mano antes de continuar por el canal correspondiente."
        if "pago" in text or "cobro" in text:
            return "Sobre el pago de la factura, puedo ayudarte a ordenar la consulta de forma general: fecha de pago, medio utilizado, comprobante y período facturado. No tengo acceso operativo a un sistema de facturación desde esta demo."
        return "Sobre la factura, puedo orientarte de forma general sin consultar un sistema de facturación. Para avanzar, decime si querés revisar importe, vencimiento, pago o un reclamo ya iniciado."
    return "Te puedo orientar paso a paso. Contame el tema concreto que querés resolver y te ayudo a ordenar el próximo movimiento."


def _should_continue_previous_capability(message: str) -> bool:
    text = message.lower()
    return any(
        marker in text
        for marker in (
            "48",
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


def _project_insurance_response(*, text: str, capability: str, plan: Mapping[str, Any], memory: ConversationProductMemory) -> str:
    if _is_billing_message(text):
        return _project_generic_response(text=text, memory=memory)
    claim_type = memory.claim_type or ("cristales" if capability == "insurance.glass" else None)
    if "persona" in text or "representante" in text or plan.get("next_action") == "prepare_handoff":
        return _handoff_response(memory=memory)
    if "48" in text and (claim_type == "cristales" or "cristal" in text):
        return "Si ya pasaron más de 48 horas hábiles desde la denuncia de cristales, el próximo paso es pedir revisión con el número de trámite y confirmar que las fotos/documentación estén cargadas en el canal oficial."
    if "te la comparto" in text or "documentación" in text or "documentacion" in text:
        return "Por acá no hace falta que me la compartas. Tenela lista y cargala o verificá que ya esté subida en el mismo canal donde iniciaste la denuncia."
    if "ya me dijiste" in text or "ya dijiste" in text:
        return "Tenés razón. No repito la lista: en este punto ordenamos el reclamo y preparamos el resumen para que revisen la demora."
    if "actúes" in text or "actues" in text or "cliente" in text:
        if claim_type == "cristales":
            return "Entendido. Sigo como atención al cliente: tomo que el trámite es por cristales y que la denuncia ya fue cargada desde la app. Ahora revisamos el próximo paso sin volver al inicio."
        return "Entendido. Sigo como atención al cliente y te voy guiando con el trámite sin volver a explicar el sistema."
    if "cristal" in text or "vidrio" in text or claim_type == "cristales":
        return "Para cristales, lo importante es que la denuncia esté cargada, las fotos se vean claras y el trámite tenga una autorización o próximo paso. Si eso ya está y no hubo respuesta, corresponde pedir revisión."
    return "Te oriento con el trámite. Contame qué parte quedó trabada y avanzamos desde ahí."


def _handoff_response(*, memory: ConversationProductMemory) -> str:
    if memory.claim_type == "cristales":
        return "Te preparo un resumen: denuncia de cristales cargada desde la app, documentación/fotos disponibles y demora mayor a 48 horas hábiles. Con eso una persona puede continuar sin que repitas todo."
    return "Te preparo un resumen breve con el motivo de contacto, lo que ya contaste y el próximo paso esperado para que una persona continúe la gestión."


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
