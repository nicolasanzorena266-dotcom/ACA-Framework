from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize

PUBLIC_DEMO_USABILITY_CONTRACT = "public_demo_usability.v1"
PUBLIC_DEMO_THOUGHT_CONTRACT = "public_demo_thought_view.v1"


@dataclass(frozen=True)
class PublicDemoUsabilitySpec:
    """Human-first public demo usability contract.

    The public Studio should show behavior and decisions, not implementation.
    Raw Runtime payloads remain available to tests and API consumers, but the
    browser surface must default to a readable operational explanation.
    """

    product_name: str = "ACA Studio"
    public_surface: str = "public_hosted_demo"

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": PUBLIC_DEMO_USABILITY_CONTRACT,
                "status": "ready",
                "product": {
                    "name": self.product_name,
                    "surface": self.public_surface,
                    "experience_goal": "first_user_understands_runtime_behavior_without_reading_json",
                },
                "rules": {
                    "raw_json_default_visible": False,
                    "code_visible_in_public_ui": False,
                    "thought_view": "modal_only",
                    "thought_view_close_control": True,
                    "buttons_must_have_actions": True,
                    "business_logic_location": "runtime",
                    "external_ai_required": False,
                },
                "primary_panels": [
                    {
                        "id": "human_runtime_reading",
                        "title": "Lectura humana del runtime",
                        "purpose": "Explain what ACA understood, which domain it used, what decision it made and what it still needs.",
                    },
                    {
                        "id": "simulation_phone",
                        "title": "Simulación",
                        "purpose": "Show the conversation without exposing Runtime internals.",
                    },
                    {
                        "id": "domain_metrics_deploy",
                        "title": "Domain / Metrics / Deploy",
                        "purpose": "Summarize operational status in short cards.",
                    },
                ],
                "button_actions": {
                    "Studio": "scroll_home",
                    "Simulación": "focus_message_input",
                    "Domain Packs": "open_domain_pack_modal",
                    "Trace": "open_thought_modal",
                    "Métricas": "open_metrics_modal",
                    "Deploy": "open_deploy_modal",
                    "customer_support": "select_support_pack_and_explain",
                    "operations_basic": "select_operations_pack_and_explain",
                    "runtime_demo": "select_general_runtime_demo",
                    "Ejecutar demo": "run_default_domain_flow",
                    "Ver diagnóstico": "open_diagnostic_modal",
                    "Ver pensamiento": "open_thought_modal",
                    "Refrescar": "refresh_runtime_state",
                },
                "capability_answer": {
                    "trigger_examples": ["que podes hacer", "qué podés hacer", "como funcionas"],
                    "response": "ACA puede ejecutar simulaciones deterministas sobre dominios cargados, interpretar intención, elegir un flujo, aplicar políticas, generar trace y mostrar métricas sin depender de IA externa.",
                },
                "non_goals": [
                    "no code exposure in the public Studio",
                    "no raw JSON wall in the primary demo surface",
                    "no chatbot positioning",
                    "no LLM dependency for the public demo",
                ],
                "metadata": {
                    "sprint": 70,
                    "epic": "Public Demo Stabilization",
                    "reason": "Public demo was technically valid but not human-readable enough.",
                },
            }
        )


def build_public_demo_usability() -> Dict[str, Any]:
    return PublicDemoUsabilitySpec().to_dict()


def build_public_demo_thought_view(*, execution: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(execution or {})
    runtime_execution = payload.get("runtime_execution") if isinstance(payload.get("runtime_execution"), Mapping) else {}
    trace = payload.get("trace_summary") if isinstance(payload.get("trace_summary"), Mapping) else {}
    intent = payload.get("matched_intent") if isinstance(payload.get("matched_intent"), Mapping) else {}
    domain = payload.get("domain") if isinstance(payload.get("domain"), Mapping) else {}
    flow = payload.get("selected_flow") if isinstance(payload.get("selected_flow"), Mapping) else {}
    entities = payload.get("entities") if isinstance(payload.get("entities"), Mapping) else {}

    return sanitize(
        {
            "contract": PUBLIC_DEMO_THOUGHT_CONTRACT,
            "status": "ready",
            "code_visible": False,
            "raw_json_default_visible": False,
            "steps": [
                {
                    "id": "input",
                    "label": "Entrada",
                    "value": payload.get("message") or "Sin mensaje",
                    "explanation": "Mensaje recibido por la demo pública.",
                },
                {
                    "id": "intent",
                    "label": "Interpretación",
                    "value": intent.get("description") or intent.get("name") or "Sin intención específica",
                    "explanation": "ACA intenta asociar el mensaje a una intención del dominio activo.",
                },
                {
                    "id": "domain",
                    "label": "Dominio",
                    "value": domain.get("pack") or domain.get("domain") or "runtime_demo",
                    "explanation": "El dominio aporta vocabulario y flujos sin acoplar código al Studio.",
                },
                {
                    "id": "flow",
                    "label": "Flujo",
                    "value": flow.get("description") or flow.get("name") or "flujo determinista",
                    "explanation": "Flujo elegido para orientar la respuesta.",
                },
                {
                    "id": "confidence",
                    "label": "Confianza",
                    "value": intent.get("confidence", 0),
                    "explanation": "Si la confianza es baja, ACA pide más datos en vez de inventar.",
                },
                {
                    "id": "trace",
                    "label": "Trace",
                    "value": trace.get("trace_id") or runtime_execution.get("trace_id") or "visible_after_execution",
                    "explanation": "Referencia observable de la ejecución sin mostrar código interno.",
                },
            ],
            "entities": dict(entities),
            "metadata": {
                "business_logic": "runtime_only",
                "llm_used": False,
                "public_ui_exposes_code": False,
            },
        }
    )


def validate_public_demo_usability(*, spec: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(spec or build_public_demo_usability())
    rules = dict(payload.get("rules", {}))
    errors: list[str] = []

    if payload.get("contract") != PUBLIC_DEMO_USABILITY_CONTRACT:
        errors.append("invalid public demo usability contract")
    if rules.get("raw_json_default_visible") is not False:
        errors.append("raw JSON must not be visible by default")
    if rules.get("code_visible_in_public_ui") is not False:
        errors.append("public UI must not expose code")
    if rules.get("thought_view") != "modal_only":
        errors.append("thought view must be modal only")
    if rules.get("buttons_must_have_actions") is not True:
        errors.append("all clickable controls must have actions")
    if rules.get("business_logic_location") != "runtime":
        errors.append("business logic must stay in runtime")
    if rules.get("external_ai_required") is not False:
        errors.append("public demo must not require external AI")

    return sanitize({"valid": not errors, "errors": errors, "spec": payload})
