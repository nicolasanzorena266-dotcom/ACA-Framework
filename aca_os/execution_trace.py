from __future__ import annotations

import json
from copy import deepcopy
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
    semantic_authority: Dict[str, Any] = field(default_factory=dict)
    semantic_projection: Dict[str, Any] = field(default_factory=dict)
    semantic_authority_pilot: Dict[str, Any] = field(default_factory=dict)
    conversational_goal_authority: Dict[str, Any] = field(default_factory=dict)

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
        semantic_authority = _semantic_authority_from_state(state)
        semantic_projection = _semantic_projection_from_state(state)
        semantic_authority_pilot = _semantic_authority_pilot_from_state(state)
        conversational_goal_authority = _conversational_goal_authority_from_state(
            state
        )
        if semantic_authority.get("available"):
            timestamps = semantic_authority.get("timestamps", {})
            trace_events.append(
                TraceEvent(
                    index=0,
                    component="semantic_authority",
                    operation="SEMANTIC_REPRESENTATION_SHADOW",
                    timestamp=str(timestamps.get("started_at") or utc_now_iso()),
                    duration_ms=float(semantic_authority.get("semantic_latency_ms") or 0.0),
                    input={
                        "turn_id": (
                            semantic_authority.get("semantic_trace", {}) or {}
                        ).get("turn_id"),
                        "authority_mode": semantic_authority.get("authority_mode"),
                    },
                    output=semantic_authority.get("semantic_trace", {}),
                    metadata={
                        "semantic_representation_id": semantic_authority.get("semantic_representation_id"),
                        "semantic_version": semantic_authority.get("semantic_version"),
                        "semantic_projection_hash": semantic_authority.get("semantic_projection_hash"),
                        "semantic_authority_mode": semantic_authority.get("semantic_authority_mode"),
                        "decision_influence": False,
                        "state_mutation": False,
                        "timestamps": dict(timestamps),
                    },
                )
            )
        if semantic_projection.get("available"):
            timestamps = semantic_projection.get("timestamps", {})
            trace_events.append(
                TraceEvent(
                    index=len(trace_events),
                    component="semantic_projector",
                    operation="SEMANTIC_PROJECTION_SHADOW",
                    timestamp=str(timestamps.get("projected_at") or utc_now_iso()),
                    input={
                        "semantic_representation_id": semantic_projection.get("semantic_representation_id"),
                        "authority_mode": semantic_projection.get("authority_mode"),
                    },
                    output={
                        "semantic_projection": semantic_projection.get("semantic_projection", {}),
                        "legacy_projection": semantic_projection.get("legacy_projection", {}),
                        "projection_diff": semantic_projection.get("projection_diff", {}),
                        "metrics": semantic_projection.get("metrics", {}),
                    },
                    metadata={
                        "semantic_projection_id": semantic_projection.get("semantic_projection_id"),
                        "semantic_projection_version": semantic_projection.get("semantic_projection_version"),
                        "semantic_projection_hash": semantic_projection.get("semantic_projection_hash"),
                        "comparison_hash": (
                            semantic_projection.get("comparison", {}) or {}
                        ).get("projection_hash"),
                        "semantic_authority_mode": semantic_projection.get("semantic_authority_mode"),
                        "decision_influence": False,
                        "state_mutation": False,
                        "timestamps": dict(timestamps),
                    },
                )
            )
        if semantic_authority_pilot:
            trace_events.append(
                TraceEvent(
                    index=len(trace_events),
                    component="semantic_authority",
                    operation="SEMANTIC_AUTHORITY_VERTICAL_PILOT",
                    input={
                        "consumer": semantic_authority_pilot.get("consumer"),
                        "legacy_value": semantic_authority_pilot.get("legacy_value", {}),
                        "semantic_value": semantic_authority_pilot.get("semantic_value", {}),
                    },
                    output={
                        "authority_mode": semantic_authority_pilot.get("authority_mode"),
                        "authority_selected": semantic_authority_pilot.get("authority_selected"),
                        "authority_reason": semantic_authority_pilot.get("authority_reason"),
                        "selected_value": semantic_authority_pilot.get("selected_value", {}),
                        "rollback_reason": semantic_authority_pilot.get("rollback_reason"),
                    },
                    metadata={
                        "field_diff": semantic_authority_pilot.get("field_diff", []),
                        "confidence": semantic_authority_pilot.get("confidence"),
                        "projection_valid": semantic_authority_pilot.get("projection_valid"),
                        "critical_errors": semantic_authority_pilot.get("critical_errors", []),
                        "forbidden_differences": semantic_authority_pilot.get(
                            "forbidden_differences", []
                        ),
                        "atomic_selection": semantic_authority_pilot.get("atomic_selection"),
                        "mixed_authority": semantic_authority_pilot.get("mixed_authority"),
                        "firewall_package": semantic_authority_pilot.get("firewall_package"),
                        "legacy_capture_phase": semantic_authority_pilot.get(
                            "legacy_capture_phase"
                        ),
                        "downstream_text_access": semantic_authority_pilot.get(
                            "downstream_text_access"
                        ),
                    },
                )
            )
        if conversational_goal_authority:
            trace_events.append(
                TraceEvent(
                    index=len(trace_events),
                    component="conversation_state",
                    operation="SEMANTIC_FIREWALL_CONVERSATIONAL_GOAL",
                    input={
                        "consumer": conversational_goal_authority.get("consumer"),
                        "legacy_value": conversational_goal_authority.get(
                            "legacy_value", {}
                        ),
                        "semantic_value": conversational_goal_authority.get(
                            "semantic_value", {}
                        ),
                    },
                    output={
                        "authority_mode": conversational_goal_authority.get(
                            "authority_mode"
                        ),
                        "authority_selected": conversational_goal_authority.get(
                            "authority_selected"
                        ),
                        "authority_reason": conversational_goal_authority.get(
                            "authority_reason"
                        ),
                        "selected_value": conversational_goal_authority.get(
                            "selected_value", {}
                        ),
                        "rollback_reason": conversational_goal_authority.get(
                            "rollback_reason"
                        ),
                    },
                    metadata={
                        "field_diff": conversational_goal_authority.get(
                            "field_diff", []
                        ),
                        "confidence": conversational_goal_authority.get("confidence"),
                        "agreement": conversational_goal_authority.get("agreement"),
                        "state_delta_parity": conversational_goal_authority.get(
                            "state_delta_parity"
                        ),
                        "projection_valid": conversational_goal_authority.get(
                            "projection_valid"
                        ),
                        "atomic_selection": conversational_goal_authority.get(
                            "atomic_selection"
                        ),
                        "mixed_authority": conversational_goal_authority.get(
                            "mixed_authority"
                        ),
                        "firewall_package": conversational_goal_authority.get(
                            "firewall_package"
                        ),
                        "downstream_text_access": conversational_goal_authority.get(
                            "downstream_text_access"
                        ),
                    },
                )
            )

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
            semantic_authority=semantic_authority,
            semantic_projection=semantic_projection,
            semantic_authority_pilot=semantic_authority_pilot,
            conversational_goal_authority=conversational_goal_authority,
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
            "semantic_authority": deepcopy(self.semantic_authority),
            "semantic_projection": deepcopy(self.semantic_projection),
            "semantic_authority_pilot": deepcopy(self.semantic_authority_pilot),
            "conversational_goal_authority": deepcopy(
                self.conversational_goal_authority
            ),
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
        "EXECUTION_AUTHORITY": "runtime_execution_authority",
        "EXECUTION_STEP_OUTCOMES": "execution_step_outcomes",
        "RUNTIME_EXECUTOR_SHADOW": "runtime_executor",
        "RUNTIME_EXECUTOR_ADOPTION": "runtime_executor",
        "DECISION_GRAPH": "decision_graph_engine",
        "MISSION_CREATE": "mission_manager",
        "MISSION_UPDATE": "mission_manager",
        "POLICY_ESCALATE": "policy_manager",
        "POLICY_RESULT": "policy_manager",
        "TOOL_EVIDENCE": "tool_engine",
        "MEMORY_CONSOLIDATE": "memory_engine",
        "CONTEXT_BUILD": "context_manager",
        "SEMANTIC_REPRESENTATION_SHADOW": "semantic_authority",
        "SEMANTIC_PROJECTION_SHADOW": "semantic_projector",
        "SEMANTIC_AUTHORITY_VERTICAL_PILOT": "semantic_authority",
    }
    return mapping.get(operation, "runtime")


def _semantic_authority_from_state(state: CognitiveState) -> Dict[str, Any]:
    runtime_record = state.facts.get("conversation_state_runtime", {})
    if not isinstance(runtime_record, dict):
        return {}
    semantic_shadow = runtime_record.get("semantic_shadow", {})
    return deepcopy(semantic_shadow) if isinstance(semantic_shadow, dict) else {}


def _semantic_projection_from_state(state: CognitiveState) -> Dict[str, Any]:
    runtime_record = state.facts.get("conversation_state_runtime", {})
    if not isinstance(runtime_record, dict):
        return {}
    semantic_projection = runtime_record.get("semantic_projection_shadow", {})
    return deepcopy(semantic_projection) if isinstance(semantic_projection, dict) else {}


def _semantic_authority_pilot_from_state(state: CognitiveState) -> Dict[str, Any]:
    runtime_record = state.facts.get("conversation_state_runtime", {})
    if not isinstance(runtime_record, dict):
        return {}
    pilot = runtime_record.get("semantic_authority_pilot", {})
    return deepcopy(pilot) if isinstance(pilot, dict) else {}


def _conversational_goal_authority_from_state(
    state: CognitiveState,
) -> Dict[str, Any]:
    runtime_record = state.facts.get("conversation_state_runtime", {})
    if not isinstance(runtime_record, dict):
        return {}
    authority = runtime_record.get("conversational_goal_authority", {})
    return deepcopy(authority) if isinstance(authority, dict) else {}
