from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_os.execution_trace import sanitize
from aca_os.introspection import RuntimeIntrospectionSnapshot


@dataclass(frozen=True)
class StudioPanel:
    """Small, transport-neutral panel consumed by ACA Studio clients."""

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
    """ACA Studio MVP view model.

    The Studio is intentionally a read-only client of the Runtime
    Introspection API. It does not inspect runtime internals directly.
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
    body {{ font-family: Arial, sans-serif; margin: 32px; background: #111; color: #eee; }}
    h1 {{ margin-bottom: 4px; }}
    .meta {{ color: #aaa; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .panel {{ border: 1px solid #333; border-radius: 12px; padding: 16px; background: #181818; }}
    .panel h2 {{ font-size: 18px; margin-top: 0; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #0b0b0b; padding: 12px; border-radius: 8px; }}
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
    """Build the first ACA Studio MVP view from an introspection snapshot."""
    data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
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
            id="components",
            title="Components",
            kind="table",
            data=data.get("components", []),
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
        StudioPanel(
            id="metrics",
            title="Metrics",
            kind="metrics",
            data=data.get("metrics", {}),
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
        },
    )


def export_studio_view(view: StudioView, *, format: str = "dict") -> Dict[str, Any] | str:
    if format == "dict":
        return view.to_dict()
    if format == "json":
        return view.to_json()
    if format == "html":
        return view.to_html()
    raise ValueError(f"Unsupported Studio export format: {format}")


def _render_panel(panel: Dict[str, Any]) -> str:
    title = html.escape(str(panel.get("title", "Panel")))
    kind = html.escape(str(panel.get("kind", "data")))
    data = html.escape(json.dumps(panel.get("data"), ensure_ascii=False, indent=2))
    return f'<article class="panel"><h2>{title}</h2><div class="meta">{kind}</div><pre>{data}</pre></article>'
