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


@dataclass
class PublicConversationProductLayer:
    runtime: PluginRuntime
    conversation_capabilities: Dict[str, str] = field(default_factory=dict)

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
        }

    def run(
        self,
        *,
        message: str = "",
        conversation_id: str = "public-conversation",
        conversation_mode: str = "client_support",
        public_action_id: str | None = None,
    ) -> Dict[str, Any]:
        action_plugin_id: str | None = None
        action: Dict[str, Any] | None = None
        requested_capability: str | None = None
        if public_action_id:
            action_plugin_id, action = self._find_action(public_action_id)
            requested_capability = action["capability"] if action else None
            if action and not action.get("enabled", True):
                return self._disabled_action_response(
                    action=action,
                    conversation_id=conversation_id,
                    conversation_mode=conversation_mode,
                )
        if requested_capability is None and _should_continue_previous_capability(message):
            requested_capability = self.conversation_capabilities.get(conversation_id)

        result = self.runtime.process(
            message,
            conversation_id=conversation_id,
            requested_capability=requested_capability,
            public_action_id=public_action_id,
            conversation_mode=conversation_mode,
        )
        response = self._project_response(message=message, result=result.to_dict(), action=action)
        response = apply_exposure_filter(response, conversation_mode=conversation_mode)
        response = apply_capability_claim_filter(response)
        active_plugin = result.route.selected_plugin_id or action_plugin_id
        if result.route.selected_capability:
            self.conversation_capabilities[conversation_id] = result.route.selected_capability
        return {
            "contract": "public_conversation_product_layer.run.v1",
            "conversation_id": conversation_id,
            "request_id": result.request_id,
            "conversation_mode": conversation_mode,
            "input_type": "action" if public_action_id else "message",
            "public_action_id": public_action_id,
            "active_plugin_id": active_plugin,
            "active_capability": result.route.selected_capability or requested_capability,
            "response": response,
            "public_actions": self._actions_for_plugin(active_plugin),
            "public_trace": build_public_trace(result.to_dict()),
            "diagnostic_view": build_diagnostic_view(result.to_dict()),
            "developer_trace": result.trace,
            "hook_execution": dict(result.hook_execution),
        }

    def _disabled_action_response(
        self,
        *,
        action: Mapping[str, Any],
        conversation_id: str,
        conversation_mode: str,
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
            "active_plugin_id": None,
            "active_capability": action["capability"],
            "response": apply_capability_claim_filter(response),
            "public_actions": self.contract()["public_actions"],
            "public_trace": {
                "trace_type": "public_trace.v1",
                "conversation_id": conversation_id,
                "request_id": request_id,
                "steps": ["Identifiqué la acción", "Validé que no está activa", "Preparé una alternativa segura"],
            },
            "diagnostic_view": {"status": "action_disabled", "capability": action["capability"]},
            "developer_trace": {
                "active_plugin_id": None,
                "active_capability": action["capability"],
                "events": [],
                "disabled_reason": action.get("disabled_reason"),
            },
            "hook_execution": {"semantic": False, "policy": False, "planner": False},
        }

    def _find_action(self, action_id: str) -> tuple[str | None, Dict[str, Any] | None]:
        for plugin in self.runtime.plugin_registry.all():
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

    def _project_response(self, *, message: str, result: Mapping[str, Any], action: Mapping[str, Any] | None) -> str:
        route = result.get("route") or {}
        plugin_id = route.get("selected_plugin_id")
        capability = route.get("selected_capability")
        text = message.lower()
        plan = result.get("plan") or {}
        if action and action.get("id") == "prepare_handoff":
            return "Te preparo un resumen breve para que una persona continúe la gestión sin que tengas que repetir todo."
        if plugin_id == "galicia.insurance":
            return _project_insurance_response(text=text, capability=str(capability or ""), plan=plan)
        return "Te puedo orientar paso a paso. Contame qué querés resolver y te ayudo a ordenar el próximo movimiento."


def _should_continue_previous_capability(message: str) -> bool:
    text = message.lower()
    return any(marker in text for marker in ("48", "ya me dijiste", "ya dijiste", "documentación", "documentacion", "cliente"))


def _project_insurance_response(*, text: str, capability: str, plan: Mapping[str, Any]) -> str:
    if "persona" in text or "representante" in text or plan.get("next_action") == "prepare_handoff":
        return "Puedo prepararte un resumen para que una persona continúe con el tipo de trámite, lo que ya cargaste y el motivo del reclamo."
    if "48" in text and ("cristal" in text or capability == "insurance.glass"):
        return "Si ya pasaron más de 48 horas hábiles desde la denuncia de cristales, conviene pedir revisión del caso con el número de trámite y la documentación cargada."
    if "te la comparto" in text or "documentación" in text or "documentacion" in text:
        return "No hace falta que me la envíes por este chat. Lo más seguro es cargarla o verificarla en el mismo canal donde iniciaste la denuncia."
    if "ya me dijiste" in text or "ya dijiste" in text:
        return "Tenés razón; no repito la lista. En este punto corresponde ordenar el reclamo y preparar el resumen para revisión."
    if "cristal" in text or "vidrio" in text or capability == "insurance.glass":
        return "Para cristales, el foco es confirmar que la denuncia esté cargada, que las fotos sean claras y que el trámite tenga un próximo paso visible."
    return "Te oriento con el trámite: primero identificamos el tipo de siniestro, después qué documentación ya está cargada y finalmente el próximo paso."


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


def build_diagnostic_view(result: Mapping[str, Any]) -> Dict[str, Any]:
    route = result.get("route") or {}
    return {
        "trace_type": "diagnostic_view.v1",
        "selected_plugin_id": route.get("selected_plugin_id"),
        "selected_capability": route.get("selected_capability"),
        "hook_execution": dict(result.get("hook_execution") or {}),
        "plan": dict(result.get("plan") or {}),
        "policy_decision": dict(result.get("policy_decision") or {}),
    }


def build_public_conversation_product_layer(root: str | Path = "plugins") -> Dict[str, Any]:
    return PublicConversationProductLayer.from_path(root).contract()


def run_public_conversation_product_layer(
    *,
    message: str = "",
    conversation_id: str = "public-conversation",
    conversation_mode: str = "client_support",
    public_action_id: str | None = None,
    root: str | Path = "plugins",
) -> Dict[str, Any]:
    layer = PublicConversationProductLayer.from_path(root)
    return layer.run(
        message=message,
        conversation_id=conversation_id,
        conversation_mode=conversation_mode,
        public_action_id=public_action_id,
    )
