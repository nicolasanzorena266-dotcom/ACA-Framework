from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


STUDIO_UX_STRUCTURE_CONTRACT = "studio_ux_structure.v1"


@dataclass(frozen=True)
class StudioUXNavItem:
    """One stable Studio navigation item.

    Navigation is UI structure only. It points to Runtime/API capabilities but
    does not execute them and does not own business logic.
    """

    id: str
    label: str
    icon: str
    panel: str
    capability: str
    primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "panel": self.panel,
            "capability": self.capability,
            "primary": self.primary,
        }


@dataclass(frozen=True)
class StudioUXPanel:
    """One visual panel definition for ACA Studio."""

    id: str
    title: str
    role: str
    data_source: str
    priority: int
    description: str
    region: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "role": self.role,
            "data_source": self.data_source,
            "priority": self.priority,
            "description": self.description,
            "region": self.region,
        }


@dataclass(frozen=True)
class StudioUXMetricCard:
    """One Studio status card bound to Runtime API data."""

    id: str
    label: str
    source_path: str
    fallback: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "source_path": self.source_path,
            "fallback": self.fallback,
        }


@dataclass(frozen=True)
class StudioUXStructure:
    """Stable Studio UX structure contract.

    This is the bridge between Runtime Interfaces and the browser shell. It is
    deliberately declarative: layout, panels, labels, and source endpoints only.
    """

    theme: Mapping[str, Any]
    navigation: tuple[StudioUXNavItem, ...]
    panels: tuple[StudioUXPanel, ...]
    metric_cards: tuple[StudioUXMetricCard, ...]
    runtime_binding: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": STUDIO_UX_STRUCTURE_CONTRACT,
                "shell": {
                    "name": "ACA Studio",
                    "subtitle": "Runtime Cognitive Interface",
                    "layout": "sidebar_two_column_workspace",
                    "visual_direction": "clean_light_operational_dashboard",
                    "inspiration": "cx_lab_operational_tooling",
                },
                "theme": dict(self.theme),
                "navigation": [item.to_dict() for item in self.navigation],
                "panels": [panel.to_dict() for panel in self.panels],
                "metric_cards": [card.to_dict() for card in self.metric_cards],
                "runtime_binding": dict(self.runtime_binding or {}),
                "metadata": {
                    "source": "runtime_api",
                    "business_logic": "runtime_only",
                    "style_locked": False,
                    "structure_locked": True,
                    **dict(self.metadata),
                },
            }
        )


def build_studio_ux_structure(*, runtime_binding: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Build the Sprint 57 Studio UX structure.

    The returned object is consumed by Studio and tests. It can be rendered by
    any web shell without reaching into Runtime internals.
    """
    theme = {
        "mode": "light",
        "background": "#f7f9fc",
        "surface": "#ffffff",
        "surface_muted": "#f3f6fb",
        "text": "#06111f",
        "text_muted": "#5d6b82",
        "primary": "#2563eb",
        "secondary": "#7c3aed",
        "success": "#16a34a",
        "warning": "#f97316",
        "danger": "#ef4444",
        "border": "#d7e0ee",
        "radius": "16px",
        "shadow": "0 20px 55px rgba(15, 23, 42, 0.08)",
    }
    navigation = (
        StudioUXNavItem("studio", "Studio", "⌂", "workspace", "studio.runtime.binding", True),
        StudioUXNavItem("simulation", "Simulación", "▣", "simulation", "demo.domain_flow.run", True),
        StudioUXNavItem("domain_packs", "Domain Packs", "◇", "domain", "domain_pack.list"),
        StudioUXNavItem("trace", "Trace", "⌁", "trace", "trace.read"),
        StudioUXNavItem("metrics", "Métricas", "▥", "metrics", "metrics.read"),
        StudioUXNavItem("deploy", "Deploy", "⇧", "deploy", "public_demo.readiness.read"),
    )
    panels = (
        StudioUXPanel(
            "runtime_overview",
            "Estado del runtime",
            "status_summary",
            "/studio/binding",
            10,
            "Runtime ready state, identifiers, loaded components and domain packs.",
            "top",
        ),
        StudioUXPanel(
            "simulation_input",
            "Simulación cognitiva",
            "input_runner",
            "/demo/domain-flow",
            20,
            "Primary human test input for the active demo domain flow.",
            "main_left",
        ),
        StudioUXPanel(
            "execution_context",
            "Contexto de ejecución",
            "context_card",
            "/studio/binding",
            30,
            "Domain Pack context, selected pack, runtime binding and execution notes.",
            "main_right",
        ),
        StudioUXPanel(
            "last_output",
            "Output",
            "result_card",
            "/studio/binding/run",
            40,
            "Last runtime response, selected program and execution status.",
            "main_right",
        ),
        StudioUXPanel(
            "trace_metrics",
            "Trace y métricas",
            "observability_grid",
            "/runtime/metrics",
            50,
            "Trace count, operation summaries, metrics and observable runtime data.",
            "bottom",
        ),
    )
    cards = (
        StudioUXMetricCard("runtime_status", "Runtime", "runtime.status", "unknown"),
        StudioUXMetricCard("components", "Componentes", "runtime.component_count", "0"),
        StudioUXMetricCard("domain_packs", "Domain Packs", "domain.pack_count", "0"),
        StudioUXMetricCard("traces", "Traces", "runtime.trace_count", "0"),
    )
    return StudioUXStructure(
        theme=theme,
        navigation=navigation,
        panels=panels,
        metric_cards=cards,
        runtime_binding=runtime_binding,
        metadata={"sprint": 57, "visual_reference": "light_cx_lab_dashboard"},
    ).to_dict()
