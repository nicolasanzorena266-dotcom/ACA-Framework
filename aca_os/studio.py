from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from aca_os.execution_trace import sanitize
from aca_os.introspection import RuntimeIntrospectionSnapshot


@dataclass(frozen=True)
class StudioPanel:
    """Transport-neutral panel consumed by ACA Studio clients.

    Panels are view models only. They never compute runtime behavior and never
    reach into component implementations. All data must come from the Runtime
    Introspection API contract.
    """

    id: str
    title: str
    kind: str
    data: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "data": sanitize(self.data),
        }


@dataclass(frozen=True)
class StudioView:
    """ACA Studio view model.

    Studio is a read-only interface over Runtime Intelligence. It consumes
    introspection, metrics, registry and trace contracts; it does not contain
    runtime decisions or mutate ACA state.
    """

    title: str
    runtime_id: str
    status: str
    panels: List[StudioPanel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "runtime_id": self.runtime_id,
            "status": self.status,
            "panels": [panel.to_dict() for panel in self.panels],
            "metadata": sanitize(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_html(self) -> str:
        payload = self.to_dict()
        panel_html = "\n".join(_render_panel(panel) for panel in payload["panels"])
        raw_json = html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>{html.escape(self.title)}</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ font-family: Arial, sans-serif; margin: 32px; background: #101114; color: #eee; }}
    h1 {{ margin-bottom: 4px; }}
    .meta {{ color: #aaa; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .panel {{ border: 1px solid #30323a; border-radius: 14px; padding: 16px; background: #181a20; }}
    .panel h2 {{ font-size: 18px; margin: 0 0 6px 0; }}
    .kind {{ color: #aaa; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 12px; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #0b0c10; padding: 12px; border-radius: 8px; overflow: auto; }}
    details {{ margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>{html.escape(self.title)}</h1>
  <div class=\"meta\">runtime_id={html.escape(self.runtime_id)} · status={html.escape(self.status)}</div>
  <section class=\"grid\">{panel_html}</section>
  <details>
    <summary>Raw Studio JSON</summary>
    <pre>{raw_json}</pre>
  </details>
</body>
</html>"""


def build_studio_view(snapshot: RuntimeIntrospectionSnapshot | Dict[str, Any]) -> StudioView:
    """Build ACA Studio from the Runtime Introspection API contract."""
    data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
    intelligence = build_studio_intelligence(data)

    panels = [
        StudioPanel(
            id="session",
            title="Session",
            kind="summary",
            data={
                "runtime_id": data.get("runtime_id"),
                "status": data.get("status"),
                "conversation_id": data.get("last_state", {}).get("conversation_id"),
                "response": data.get("last_state", {}).get("response"),
            },
        ),
        StudioPanel(
            id="runtime_health",
            title="Runtime Health",
            kind="health",
            data=intelligence["runtime_health"],
        ),
        StudioPanel(
            id="decision_graph",
            title="Decision Graph",
            kind="graph",
            data=intelligence["decision_graph"],
        ),
        StudioPanel(
            id="metrics",
            title="Metrics",
            kind="metrics",
            data=intelligence["metrics"],
        ),
        StudioPanel(
            id="components",
            title="Components",
            kind="table",
            data=intelligence["components"],
        ),
        StudioPanel(
            id="component_registry",
            title="Component Registry",
            kind="registry",
            data=intelligence["component_registry"],
        ),
        StudioPanel(
            id="timeline",
            title="Timeline",
            kind="timeline",
            data=data.get("timeline", {}).get("entries", []),
        ),
        StudioPanel(
            id="trace",
            title="Execution Trace",
            kind="trace",
            data=data.get("last_trace", {}),
        ),
        StudioPanel(
            id="events",
            title="Event Bus",
            kind="events",
            data=data.get("event_bus", {}),
        ),
    ]
    return StudioView(
        title="ACA Studio MVP",
        runtime_id=str(data.get("runtime_id", "unknown")),
        status=str(data.get("status", "unknown")),
        panels=panels,
        metadata={
            "source": "runtime_introspection_api",
            "panel_count": len(panels),
            "contract": "studio_view.v1",
            "evolution_contract": "studio_runtime_intelligence.v1",
            "read_only": True,
        },
    )


def build_studio_intelligence(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Project Runtime Intelligence into stable Studio sections.

    This function only reshapes introspection data. It does not inspect runtime
    instances and does not decide runtime behavior.
    """
    data = dict(snapshot)
    metrics = _mapping(data.get("metrics"))
    registry = _mapping(data.get("component_registry"))
    components = list(data.get("components", []))
    last_state = _mapping(data.get("last_state"))
    last_trace = _mapping(data.get("last_trace"))
    event_bus = _mapping(data.get("event_bus"))
    decision_graph = _mapping(last_state.get("decision_graph"))

    active_components = _count_components_by_state(components, "active")
    component_count = int(registry.get("component_count", len(components)) or 0)
    event_count = int(event_bus.get("event_count", metrics.get("runtime_event_count", 0)) or 0)
    trace_count = _counter_value(metrics, "runtime.trace_count")
    process_count = _counter_value(metrics, "runtime.process_count")
    last_duration = _gauge_value(metrics, "runtime.last_trace_duration_ms")
    if last_duration == 0.0 and metrics.get("last_trace_duration_ms") is not None:
        last_duration = float(metrics.get("last_trace_duration_ms") or 0.0)

    health_status = "ready" if data.get("status") == "ready" else "unknown"
    if component_count and active_components < component_count:
        health_status = "degraded"

    return {
        "runtime_health": {
            "status": health_status,
            "component_count": component_count,
            "active_components": active_components,
            "event_count": event_count,
            "trace_count": trace_count,
            "process_count": process_count,
            "last_trace_duration_ms": last_duration,
            "policy_decision": last_state.get("policy_decision"),
            "timeline_entries": metrics.get("timeline_entries", 0),
        },
        "decision_graph": _graph_summary(decision_graph),
        "metrics": _metrics_summary(metrics),
        "components": _component_rows(components),
        "component_registry": {
            "component_count": component_count,
            "states": registry.get("states", {}),
            "capability_count": len(_collect_capabilities(components)),
            "capabilities": _collect_capabilities(components),
        },
        "trace": {
            "trace_id": last_trace.get("trace_id"),
            "duration_ms": last_trace.get("duration_ms"),
            "operations": last_trace.get("operations", []),
        },
    }


def export_studio_view(view: StudioView, *, format: str = "dict") -> Dict[str, Any] | str:
    if format == "dict":
        return view.to_dict()
    if format == "json":
        return view.to_json()
    if format == "html":
        return view.to_html()
    raise ValueError(f"Unsupported Studio export format: {format}")


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _count_components_by_state(components: List[Any], state: str) -> int:
    return sum(1 for component in components if _mapping(component).get("state") == state)


def _counter_value(metrics: Mapping[str, Any], name: str) -> int:
    counters = _mapping(metrics.get("counters"))
    value = _mapping(counters.get(name)).get("value", 0)
    return int(value or 0)


def _gauge_value(metrics: Mapping[str, Any], name: str) -> float:
    gauges = _mapping(metrics.get("gauges"))
    value = _mapping(gauges.get(name)).get("value", 0.0)
    return float(value or 0.0)


def _graph_summary(graph: Mapping[str, Any]) -> Dict[str, Any]:
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    selected_path = list(graph.get("selected_path", []))
    return {
        "available": bool(graph),
        "graph_id": graph.get("graph_id"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "selected_path": selected_path,
        "terminal_node": graph.get("terminal_node"),
        "nodes": nodes,
        "edges": edges,
    }


def _metrics_summary(metrics: Mapping[str, Any]) -> Dict[str, Any]:
    duration = _mapping(metrics.get("total_duration_ms"))
    return {
        "trace_count": int(metrics.get("trace_count", 0) or 0),
        "process_count": int(metrics.get("process_count", 0) or 0),
        "event_count": int(metrics.get("event_count", 0) or 0),
        "operation_count": int(metrics.get("operation_count", 0) or 0),
        "process_duration_ms": duration,
        "component_metrics": metrics.get("components", {}),
    }


def _component_rows(components: List[Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for component in components:
        item = _mapping(component)
        rows.append(
            {
                "name": item.get("name"),
                "role": item.get("role"),
                "state": item.get("state"),
                "version": item.get("version"),
                "provider": item.get("provider"),
                "capabilities": item.get("capabilities", []),
            }
        )
    return sorted(rows, key=lambda row: str(row.get("name", "")))


def _collect_capabilities(components: List[Any]) -> List[str]:
    capabilities = set()
    for component in components:
        item = _mapping(component)
        for capability in item.get("capabilities", []) or []:
            capabilities.add(str(capability))
    return sorted(capabilities)


def _render_panel(panel: Dict[str, Any]) -> str:
    title = html.escape(str(panel.get("title", "Panel")))
    kind = html.escape(str(panel.get("kind", "data")))
    data = html.escape(json.dumps(panel.get("data"), ensure_ascii=False, indent=2))
    return f'<article class="panel"><h2>{title}</h2><div class="kind">{kind}</div><pre>{data}</pre></article>'
