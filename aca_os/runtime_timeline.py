from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from aca_kernel.core.state import CognitiveState
from aca_os.event_bus import RuntimeEvent


@dataclass(frozen=True)
class RuntimeTimelineEntry:
    """Normalized runtime timeline entry for inspection and Studio previews."""

    index: int
    kind: str
    operation: str
    from_version: int | None = None
    to_version: int | None = None
    event_type: str | None = None
    source: str | None = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "operation": self.operation,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "event_type": self.event_type,
            "source": self.source,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class RuntimeTimeline:
    """Read-only normalized view of state transitions and runtime events."""

    entries: List[RuntimeTimelineEntry] = field(default_factory=list)

    @classmethod
    def from_state(
        cls,
        state: CognitiveState,
        runtime_events: Iterable[RuntimeEvent] | None = None,
    ) -> "RuntimeTimeline":
        entries: List[RuntimeTimelineEntry] = []

        for item in state.timeline:
            entries.append(
                RuntimeTimelineEntry(
                    index=len(entries),
                    kind="state_transition",
                    operation=str(item.get("operation", "UNKNOWN")),
                    from_version=item.get("from_version"),
                    to_version=item.get("to_version"),
                    payload={"changes": item.get("changes", {})},
                )
            )

        for event in runtime_events or []:
            entries.append(
                RuntimeTimelineEntry(
                    index=len(entries),
                    kind="runtime_event",
                    operation=event.type,
                    event_type=event.type,
                    source=event.source,
                    payload=event.payload,
                )
            )

        return cls(entries=entries)

    def operations(self) -> List[str]:
        return [entry.operation for entry in self.entries]

    def to_list(self) -> List[Dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": self.to_list(),
            "operations": self.operations(),
        }
