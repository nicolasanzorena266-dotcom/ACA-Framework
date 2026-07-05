from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


STUDIO_VISUAL_DESIGN_CONTRACT = "studio_visual_design.v1"


@dataclass(frozen=True)
class StudioDesignTokenGroup:
    """A named group of stable visual tokens for ACA Studio.

    The design system is intentionally declarative. Studio can consume it, tests
    can verify it, and Runtime services can expose it without moving business
    behavior into the browser layer.
    """

    name: str
    values: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "values": dict(self.values)}


@dataclass(frozen=True)
class StudioComponentStyle:
    """A visual component recipe used by the browser Studio shell."""

    id: str
    role: str
    description: str
    tokens: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "description": self.description,
            "tokens": dict(self.tokens),
        }


@dataclass(frozen=True)
class StudioVisualDesignSystem:
    """Sprint 58 visual design system contract for ACA Studio."""

    token_groups: tuple[StudioDesignTokenGroup, ...]
    components: tuple[StudioComponentStyle, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": STUDIO_VISUAL_DESIGN_CONTRACT,
                "product": {
                    "name": "ACA Studio",
                    "surface": "runtime_web_studio",
                    "visual_direction": "clean_light_operational_cx_lab",
                    "tone": "serious_operational_but_human",
                },
                "tokens": {group.name: group.values for group in self.token_groups},
                "token_groups": [group.to_dict() for group in self.token_groups],
                "components": [component.to_dict() for component in self.components],
                "accessibility": {
                    "minimum_contrast": "AA",
                    "focus_visible": True,
                    "touch_target_min_px": 40,
                    "reduced_motion_safe": True,
                    "layout": "responsive_sidebar_workspace",
                },
                "metadata": {
                    "source": "design_system_contract",
                    "business_logic": "runtime_only",
                    "style_locked": True,
                    "structure_source": "studio_ux_structure.v1",
                    **dict(self.metadata),
                },
            }
        )


def build_studio_visual_design_system() -> Dict[str, Any]:
    """Return the stable ACA Studio visual design system.

    This function owns presentation tokens only. It does not call Runtime
    services and it does not infer domain behavior.
    """

    color = StudioDesignTokenGroup(
        "color",
        {
            "background": "#f6f8fc",
            "background_radial_a": "#eef4ff",
            "background_radial_b": "#f3ecff",
            "sidebar": "#ffffff",
            "surface": "#ffffff",
            "surface_soft": "#f5f7fb",
            "surface_accent": "#edf4ff",
            "text": "#07111f",
            "text_muted": "#64748b",
            "text_subtle": "#94a3b8",
            "border": "#d9e3f2",
            "border_strong": "#b8c7dc",
            "primary": "#2563eb",
            "primary_hover": "#1d4ed8",
            "primary_soft": "#e8f0ff",
            "secondary": "#7c3aed",
            "secondary_soft": "#f0e9ff",
            "success": "#16a34a",
            "success_soft": "#e9f8ef",
            "warning": "#f97316",
            "warning_soft": "#fff3e8",
            "danger": "#ef4444",
            "danger_soft": "#fff0f0",
            "ink": "#0f172a",
            "whatsapp_green": "#0f766e",
            "conversation_bg": "#f4efe3",
        },
    )
    typography = StudioDesignTokenGroup(
        "typography",
        {
            "font_family": "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "mono_family": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
            "h1_size": "28px",
            "h1_weight": 850,
            "h2_size": "19px",
            "body_size": "14px",
            "small_size": "12px",
            "letter_tight": "-0.04em",
        },
    )
    spacing = StudioDesignTokenGroup(
        "spacing",
        {
            "page_x": "28px",
            "page_y": "24px",
            "sidebar_x": "18px",
            "card": "18px",
            "card_compact": "14px",
            "gap": "16px",
            "gap_large": "22px",
        },
    )
    shape = StudioDesignTokenGroup(
        "shape",
        {
            "radius_sm": "9px",
            "radius_md": "14px",
            "radius_lg": "18px",
            "radius_xl": "28px",
            "pill": "999px",
        },
    )
    elevation = StudioDesignTokenGroup(
        "elevation",
        {
            "card": "0 18px 48px rgba(15, 23, 42, 0.08)",
            "card_hover": "0 22px 60px rgba(15, 23, 42, 0.12)",
            "button": "0 12px 26px rgba(37, 99, 235, 0.22)",
            "phone": "0 24px 58px rgba(15, 23, 42, 0.18)",
        },
    )
    components = (
        StudioComponentStyle(
            "sidebar",
            "navigation_shell",
            "Fixed light sidebar with product identity, runtime navigation and domain modules.",
            {"background": "color.sidebar", "border": "color.border", "width": "224px"},
        ),
        StudioComponentStyle(
            "metric_card",
            "runtime_summary",
            "Compact cards for status, components, packs and traces.",
            {"background": "color.surface", "shadow": "elevation.card", "radius": "shape.radius_md"},
        ),
        StudioComponentStyle(
            "simulation_phone",
            "human_flow_preview",
            "Conversation-style simulation preview for the active domain flow.",
            {"background": "color.conversation_bg", "header": "color.whatsapp_green", "shadow": "elevation.phone"},
        ),
        StudioComponentStyle(
            "context_panel",
            "execution_context",
            "Right-side runtime context panel for trace, output and domain binding.",
            {"background": "color.surface", "accent_border": "color.primary", "radius": "shape.radius_lg"},
        ),
        StudioComponentStyle(
            "primary_button",
            "action",
            "Primary call-to-action for running simulations.",
            {"background": "color.primary", "hover": "color.primary_hover", "shadow": "elevation.button"},
        ),
    )
    return StudioVisualDesignSystem(
        token_groups=(color, typography, spacing, shape, elevation),
        components=components,
        metadata={"sprint": 58, "name_locked": "ACA Studio"},
    ).to_dict()
