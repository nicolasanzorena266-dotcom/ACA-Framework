from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from aca_kernel.core.state import CognitiveState
from aca_os.event_bus import RuntimeEvent
from aca_os.runtime_timeline import RuntimeTimeline


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def monotonic_ms(start: float, end: float | None = None) -> float:
    stop = perf_counter() if end is None else end
    return round((stop - start) * 1000, 3)


def sanitize(value: Any, *, max_depth: int = 4, max_items: int = 25, max_text: int = 500) -> Any:
    """Return a bounded JSON-safe representation for trace payloads."""
    if max_depth <= 0:
        return "<max-depth>"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        if len(value) <= max_text:
            return value
        return value[:max_text] + "...<truncated>"

    if isinstance(value, dict):
        output: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                output["<truncated>"] = f"{len(value) - max_items} more items"
                break
            output[str(key)] = sanitize(
                item,
                max_depth=max_depth - 1,
                max_items=max_items,
                max_text=max_text,
            )
        return output

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        output = [
            sanitize(item, max_depth=max_depth - 1, max_items=max_items, max_text=max_text)
            for item in items[:max_items]
        ]
        if len(items) > max_items:
            output.append(f"<truncated:{len(items) - max_items} more items>")
        return output

    if hasattr(value, "to_dict"):
        try:
            return sanitize(
                value.to_dict(),
                max_depth=max_depth - 1,
                max_items=max_items,
                max_text=max_text,
            )
        except Exception:  # pragma: no cover - defensive trace safety
            return repr(value)

    return repr(value)


@dataclass(frozen=True)
class TraceEvent:
    index: int
    component: str
    operation: str
    timestamp: str = field(default_factory=utc_now_iso)
    duration_ms: float = 0.0
    input: Any = None
    output: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "component": self.component,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "input": sanitize(self.input),
            "output": sanitize(self.output),
            "metadata": sanitize(self.metadata),
        }


@dataclass(frozen=True)
class ExecutionTrace:
    trace_id: str
    conversation_id: str
    runtime_id: str
    started_at: str
    finished_at: str
    duration_ms: float
    events: List[TraceEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(
        cls,
        state: CognitiveState,
        runtime_events: Iterable[RuntimeEvent] | None = None,
        *,
        trace_id: str | None = None,
        runtime_id: str = "runtime",
        started_at: str | None = None,
        finished_at: str | None = None,
        duration_ms: float = 0.0,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExecutionTrace":
        timeline = RuntimeTimeline.from_state(state, runtime_events)
        trace_events: List[TraceEvent] = []

        for entry in timeline.entries:
            component = _component_for_operation(entry.operation, entry.kind)
            trace_events.append(
                TraceEvent(
                    index=len(trace_events),
                    component=component,
                    operation=entry.operation,
                    input={
                        "from_version": entry.from_version,
                        "event_type": entry.event_type,
                        "source": entry.source,
                    },
                    output=entry.payload,
                    metadata={"kind": entry.kind},
                )
            )

        return cls(
            trace_id=trace_id or str(uuid4()),
            conversation_id=state.conversation_id,
            runtime_id=runtime_id,
            started_at=started_at or utc_now_iso(),
            finished_at=finished_at or utc_now_iso(),
            duration_ms=duration_ms,
            events=trace_events,
            metadata=metadata or {},
        )

    def operations(self) -> List[str]:
        return [event.operation for event in self.events]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "runtime_id": self.runtime_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "events": [event.to_dict() for event in self.events],
            "operations": self.operations(),
            "metadata": sanitize(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _component_for_operation(operation: str, kind: str) -> str:
    if kind == "runtime_event":
        if "." in operation:
            return operation.split(".", 2)[1]
        return "event_bus"

    mapping = {
        "INTENT_MATCH": "intent_matcher",
        "ACTION_PLAN": "action_planner",
        "FLOW_ROUTE": "flow_router",
        "EXECUTION_PLAN": "execution_plan",
        "MISSION_CREATE": "mission_manager",
        "MISSION_UPDATE": "mission_manager",
        "POLICY_ESCALATE": "policy_manager",
        "POLICY_RESULT": "policy_manager",
        "TOOL_EVIDENCE": "tool_engine",
        "MEMORY_CONSOLIDATE": "memory_engine",
        "CONTEXT_BUILD": "context_manager",
    }
    return mapping.get(operation, "runtime")
