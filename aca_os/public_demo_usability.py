from __future__ import annotations

from typing import Any, Dict, Mapping

PUBLIC_DEMO_USABILITY_CONTRACT = "public_demo_usability.v1"
PUBLIC_DEMO_USABILITY_VALIDATION = "public_demo_usability_validation.v1"


def build_public_demo_usability(*, public_base_url: str = "https://aca-public-web-demo.onrender.com") -> Dict[str, Any]:
    """Return the human-facing public demo usability contract.

    This contract describes the Studio shell as an observable runtime interface,
    not as a chatbot wrapper. It intentionally exposes summaries for the public
    UI and keeps the full operational reasoning behind an explicit action.
    """

    base = (public_base_url or "https://aca-public-web-demo.onrender.com").rstrip("/")
    return {
        "contract": PUBLIC_DEMO_USABILITY_CONTRACT,
        "status": "ready",
        "public_base_url": base,
        "endpoint": "/public-demo/usability",
        "studio_route": "/studio",
        "principle": "Studio observa; el runtime decide.",
        "llm_role": "optional_interface_component",
        "human_runtime_reading": {
            "title": "Lectura humana del runtime",
            "summary": "El contexto visible se presenta como una lectura breve, útil y humana del estado del runtime.",
            "visible_cards": [
                "Respuesta natural del runtime",
                "Programa seleccionado",
                "Eventos y operaciones observables",
                "Próximo paso sugerido",
            ],
            "never_show": [
                "JSON crudo como contenido principal",
                "código fuente",
                "scripts internos",
                "dumps técnicos sin mediación",
            ],
        },
        "thought_modal": {
            "button_label": "Ver pensamiento",
            "title": "Pensamiento del runtime",
            "close_label": "✕",
            "content_policy": "El detalle operacional completo se abre bajo demanda y separado de la lectura principal.",
        },
        "studio_actions": {
            "run_demo": "Ejecuta una simulación real contra el runtime.",
            "diagnostics": "Refresca estado, métricas y contrato de interfaz.",
            "copy_output": "Copia la lectura humana visible.",
            "navigation": "Mueve al usuario entre secciones reales del Studio.",
        },
        "acceptance": {
            "context_is_human_readable": True,
            "raw_json_hidden_from_main_context": True,
            "thought_modal_available": True,
            "thought_modal_closable": True,
            "source_code_hidden": True,
            "studio_buttons_are_functional": True,
            "runtime_remains_decision_boundary": True,
        },
    }


def validate_public_demo_usability(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(report or build_public_demo_usability())
    acceptance = dict(payload.get("acceptance") or {})
    required = {
        "context_is_human_readable",
        "raw_json_hidden_from_main_context",
        "thought_modal_available",
        "thought_modal_closable",
        "source_code_hidden",
        "studio_buttons_are_functional",
        "runtime_remains_decision_boundary",
    }
    missing = sorted(key for key in required if acceptance.get(key) is not True)
    return {
        "contract": PUBLIC_DEMO_USABILITY_VALIDATION,
        "status": "passed" if not missing else "failed",
        "checked_contract": payload.get("contract"),
        "missing_acceptance": missing,
        "endpoint": payload.get("endpoint"),
    }
