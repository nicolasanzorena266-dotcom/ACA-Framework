from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.execution_trace import sanitize, utc_now_iso

SESSION_SCHEMA_VERSION = "aca.session.v1"


def event_to_dict(event: Event) -> Dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "payload": sanitize(event.payload),
        "metadata": sanitize(event.metadata),
    }


def event_from_dict(data: Dict[str, Any]) -> Event:
    return Event(
        id=str(data.get("id") or uuid4()),
        type=str(data.get("type", "user_message")),
        payload=data.get("payload"),
        metadata=dict(data.get("metadata") or {}),
    )


@dataclass(frozen=True)
class ExecutionSession:
    """Serializable runtime execution capsule.

    A session is the persistence boundary for ACA executions. It stores the
    original event, final state and observability artifacts without requiring
    callers to know runtime internals.
    """

    session_id: str
    schema_version: str
    created_at: str
    runtime_id: str
    event: Dict[str, Any]
    state: Dict[str, Any]
    output: Dict[str, Any]
    trace: Dict[str, Any]
    introspection: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_runtime(
        cls,
        *,
        runtime_id: str,
        event: Event,
        state: CognitiveState,
        output: Dict[str, Any],
        trace: Dict[str, Any],
        introspection: Dict[str, Any] | None = None,
        session_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExecutionSession":
        return cls(
            session_id=session_id or str(uuid4()),
            schema_version=SESSION_SCHEMA_VERSION,
            created_at=utc_now_iso(),
            runtime_id=runtime_id,
            event=event_to_dict(event),
            state=sanitize(state.to_dict()),
            output=sanitize(output),
            trace=sanitize(trace),
            introspection=sanitize(introspection or {}),
            metadata=sanitize(metadata or {}),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionSession":
        schema_version = data.get("schema_version")
        if schema_version != SESSION_SCHEMA_VERSION:
            raise ValueError(f"Unsupported ACA session schema: {schema_version}")
        return cls(
            session_id=str(data["session_id"]),
            schema_version=str(schema_version),
            created_at=str(data["created_at"]),
            runtime_id=str(data["runtime_id"]),
            event=dict(data["event"]),
            state=dict(data["state"]),
            output=dict(data["output"]),
            trace=dict(data["trace"]),
            introspection=dict(data.get("introspection") or {}),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ExecutionSession":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "runtime_id": self.runtime_id,
            "event": sanitize(self.event),
            "state": sanitize(self.state),
            "output": sanitize(self.output),
            "trace": sanitize(self.trace),
            "introspection": sanitize(self.introspection),
            "metadata": sanitize(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_json(), encoding="utf-8")
        return destination

    def replay_event(self) -> Event:
        return event_from_dict(self.event)

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "schema_version": self.schema_version,
            "runtime_id": self.runtime_id,
            "conversation_id": self.state.get("conversation_id"),
            "event_type": self.event.get("type"),
            "response": self.output.get("response"),
            "trace_id": self.trace.get("trace_id"),
            "trace_event_count": len(self.trace.get("events", [])),
            "state_version": self.state.get("version"),
        }

    def compare(self, other: "ExecutionSession") -> Dict[str, Any]:
        left_ops = list(self.trace.get("operations", []))
        right_ops = list(other.trace.get("operations", []))
        left_facts = set((self.state.get("facts") or {}).keys())
        right_facts = set((other.state.get("facts") or {}).keys())
        return {
            "left_session_id": self.session_id,
            "right_session_id": other.session_id,
            "same_response": self.output.get("response") == other.output.get("response"),
            "same_operations": left_ops == right_ops,
            "operation_delta": {
                "left_only": [op for op in left_ops if op not in right_ops],
                "right_only": [op for op in right_ops if op not in left_ops],
            },
            "fact_key_delta": {
                "left_only": sorted(left_facts - right_facts),
                "right_only": sorted(right_facts - left_facts),
            },
            "state_version_delta": (self.state.get("version") or 0) - (other.state.get("version") or 0),
        }
