from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


STUDIO_RUNTIME_BINDING_CONTRACT = "studio_runtime_binding.v1"
STUDIO_RUNTIME_RUN_CONTRACT = "studio_runtime_binding.run.v1"


@dataclass(frozen=True)
class StudioRuntimeBinding:
    """Studio-facing Runtime binding assembled from Runtime API payloads only.

    This object is deliberately data-only. It does not build a runtime, import
    domain code, call components directly, or own business behavior. It only
    shapes Runtime API responses into a stable Studio view.
    """

    status: Mapping[str, Any]
    metrics: Mapping[str, Any]
    components: Mapping[str, Any]
    plugins: Mapping[str, Any]
    domain_packs: Mapping[str, Any]
    domain_context: Mapping[str, Any]
    endpoints: Mapping[str, Any]
    studio: Mapping[str, Any]
    last_run: Mapping[str, Any] | None = None
    errors: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        domain_pack_count = _as_int(self.domain_packs.get("pack_count"), default=0)
        loaded_domains = [pack.get("name") for pack in self.domain_packs.get("packs", []) if isinstance(pack, Mapping)]
        return sanitize(
            {
                "contract": STUDIO_RUNTIME_BINDING_CONTRACT,
                "runtime": {
                    "status": self.status.get("status"),
                    "runtime_id": self.status.get("runtime_id"),
                    "component_count": self.status.get("component_count"),
                    "plugin_count": self.status.get("plugin_count"),
                    "trace_count": self.status.get("trace_count"),
                },
                "domain": {
                    "pack_count": domain_pack_count,
                    "loaded_packs": loaded_domains,
                    "context": self.domain_context,
                },
                "metrics": self.metrics,
                "components": self.components,
                "plugins": self.plugins,
                "endpoints": self.endpoints,
                "studio": self.studio,
                "last_run": dict(self.last_run or {}),
                "errors": [dict(error) for error in self.errors],
                "metadata": {
                    "source": "runtime_api",
                    "business_logic": "runtime_only",
                    "domain_logic_embedded": False,
                },
            }
        )


@dataclass(frozen=True)
class StudioRuntimeRunBinding:
    """Studio-friendly projection of one Runtime execution result."""

    execution: Mapping[str, Any]
    refreshed_binding: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        trace = self.execution.get("execution_trace", {})
        introspection = self.execution.get("introspection", {})
        final_state = trace.get("final_state", {}) if isinstance(trace, Mapping) else {}
        return sanitize(
            {
                "contract": STUDIO_RUNTIME_RUN_CONTRACT,
                "conversation_id": self.execution.get("conversation_id"),
                "response": self.execution.get("response"),
                "status": self.execution.get("status"),
                "progress": self.execution.get("progress"),
                "trace": {
                    "trace_id": trace.get("trace_id") if isinstance(trace, Mapping) else None,
                    "runtime_id": trace.get("runtime_id") if isinstance(trace, Mapping) else None,
                    "operation_count": len(trace.get("operations", [])) if isinstance(trace, Mapping) else 0,
                    "event_count": len(trace.get("events", [])) if isinstance(trace, Mapping) else 0,
                    "final_version": final_state.get("version") if isinstance(final_state, Mapping) else None,
                },
                "introspection": {
                    "runtime_id": introspection.get("runtime_id") if isinstance(introspection, Mapping) else None,
                    "status": introspection.get("status") if isinstance(introspection, Mapping) else None,
                    "component_count": len(introspection.get("components", [])) if isinstance(introspection, Mapping) else 0,
                },
                "execution": self.execution,
                "binding": self.refreshed_binding,
                "metadata": {
                    "source": "runtime_api",
                    "business_logic": "runtime_only",
                },
            }
        )


def build_studio_runtime_binding(
    *,
    status: Mapping[str, Any],
    metrics: Mapping[str, Any],
    components: Mapping[str, Any],
    plugins: Mapping[str, Any],
    domain_packs: Mapping[str, Any],
    domain_context: Mapping[str, Any],
    endpoints: Mapping[str, Any],
    studio: Mapping[str, Any],
    last_run: Mapping[str, Any] | None = None,
    errors: tuple[Mapping[str, Any], ...] = (),
) -> Dict[str, Any]:
    return StudioRuntimeBinding(
        status=status,
        metrics=metrics,
        components=components,
        plugins=plugins,
        domain_packs=domain_packs,
        domain_context=domain_context,
        endpoints=endpoints,
        studio=studio,
        last_run=last_run,
        errors=errors,
    ).to_dict()


def build_studio_runtime_run_binding(
    *,
    execution: Mapping[str, Any],
    refreshed_binding: Mapping[str, Any],
) -> Dict[str, Any]:
    return StudioRuntimeRunBinding(execution=execution, refreshed_binding=refreshed_binding).to_dict()


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
