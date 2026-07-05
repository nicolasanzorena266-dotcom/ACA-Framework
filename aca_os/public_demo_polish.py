from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


PUBLIC_DEMO_POLISH_CONTRACT = "public_demo_polish.v1"


@dataclass(frozen=True)
class PublicDemoPrompt:
    """A safe, deterministic prompt suggestion for the public demo shell."""

    id: str
    label: str
    message: str
    domain_pack: str
    intent_hint: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "message": self.message,
            "domain_pack": self.domain_pack,
            "intent_hint": self.intent_hint,
        }


@dataclass(frozen=True)
class PublicDemoPolish:
    """Presentation contract for the public ACA Studio demo.

    This module owns public-demo copy and UX affordances only. It does not run
    Runtime behavior, classify messages, infer domains, or mutate state.
    """

    prompts: tuple[PublicDemoPrompt, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": PUBLIC_DEMO_POLISH_CONTRACT,
                "product": {
                    "name": "ACA Studio",
                    "surface": "public_web_demo",
                    "positioning": "deterministic cognitive runtime demo",
                    "visual_direction": "clean_light_operational_cx_lab",
                },
                "hero": {
                    "eyebrow": "Public runtime demo",
                    "title": "Probá ACA Studio con un dominio cargado.",
                    "subtitle": (
                        "Ejecutá una simulación, mirá el Domain Pack activo y seguí el trace "
                        "sin depender de una IA externa ni de una caja negra con moño."
                    ),
                    "primary_action": "Ejecutar demo",
                    "secondary_action": "Ver diagnóstico",
                },
                "states": {
                    "ready": "Runtime listo",
                    "loading": "Cargando runtime…",
                    "running": "Ejecutando flujo determinista…",
                    "success": "Ejecución completada",
                    "error": "No se pudo completar la ejecución",
                    "empty": "Elegí un ejemplo o escribí una consulta para iniciar.",
                },
                "prompts": [prompt.to_dict() for prompt in self.prompts],
                "output_panels": [
                    {
                        "id": "runtime_output",
                        "title": "Resultado",
                        "description": "Respuesta normalizada devuelta por el Runtime API.",
                    },
                    {
                        "id": "domain_context",
                        "title": "Dominio activo",
                        "description": "Domain Packs cargados y contexto operativo usado por la simulación.",
                    },
                    {
                        "id": "trace_metrics",
                        "title": "Trace / métricas",
                        "description": "Señales observables de la ejecución, sin lógica escondida en Studio.",
                    },
                ],
                "error_copy": {
                    "network": "El servidor local no respondió. Revisá que aca_web.py siga abierto.",
                    "bad_request": "La solicitud no tiene el formato esperado por el Runtime API.",
                    "unknown": "Error no clasificado. La demo lo muestra, no lo disfraza. Algo es algo.",
                },
                "public_demo_checks": {
                    "business_logic_location": "runtime",
                    "interface_logic_location": "studio_shell",
                    "external_ai_required": False,
                    "offline_local_mode_supported": True,
                    "trace_visible": True,
                    "domain_pack_visible": True,
                },
                "metadata": {
                    "sprint": 59,
                    "business_logic": "runtime_only",
                    "copy_locked_for_demo": True,
                    **dict(self.metadata),
                },
            }
        )


def build_public_demo_polish() -> Dict[str, Any]:
    prompts = (
        PublicDemoPrompt(
            id="ticket_status",
            label="Consultar ticket",
            message="Necesito saber el estado del ticket 12345",
            domain_pack="customer_support",
            intent_hint="ticket_status_check",
        ),
        PublicDemoPrompt(
            id="pending_docs",
            label="Documentación pendiente",
            message="Quiero saber qué documentación falta para avanzar",
            domain_pack="customer_support",
            intent_hint="missing_documentation",
        ),
        PublicDemoPrompt(
            id="ops_followup",
            label="Seguimiento operativo",
            message="Mostrame próximos pasos para este caso operativo",
            domain_pack="operations_basic",
            intent_hint="operational_followup",
        ),
    )
    return PublicDemoPolish(prompts=prompts).to_dict()


def validate_public_demo_polish(polish: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(polish or build_public_demo_polish())
    errors: list[str] = []

    if payload.get("contract") != PUBLIC_DEMO_POLISH_CONTRACT:
        errors.append("invalid public demo polish contract")
    if payload.get("product", {}).get("name") != "ACA Studio":
        errors.append("product name must remain ACA Studio")
    if payload.get("metadata", {}).get("business_logic") != "runtime_only":
        errors.append("public demo polish must not own business logic")
    if payload.get("public_demo_checks", {}).get("business_logic_location") != "runtime":
        errors.append("runtime business logic must stay in runtime")
    if payload.get("public_demo_checks", {}).get("external_ai_required") is not False:
        errors.append("public demo must not require external AI")
    if not payload.get("prompts"):
        errors.append("public demo polish must include at least one prompt")
    if not payload.get("output_panels"):
        errors.append("public demo polish must include output panels")

    return {
        "valid": not errors,
        "errors": errors,
        "polish": sanitize(payload),
    }
