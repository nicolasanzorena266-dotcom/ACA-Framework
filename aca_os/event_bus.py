from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List
from uuid import uuid4


@dataclass(frozen=True)
class RuntimeEvent:
    """Internal observable event emitted by the ACA runtime."""

    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "runtime"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }


EventHandler = Callable[[RuntimeEvent], None]


class EventBus:
    """Small in-process event bus for zero-cost runtime observability.

    The bus is intentionally passive: publishing an event must never change the
    runtime decision path. Handlers are best-effort observers.
    """

    def __init__(self) -> None:
        self._events: List[RuntimeEvent] = []
        self._handlers: Dict[str, List[EventHandler]] = {}

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any] | None = None,
        *,
        source: str = "runtime",
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            type=event_type,
            payload=payload or {},
            source=source,
        )
        self._events.append(event)

        for handler in [*self._handlers.get(event_type, []), *self._handlers.get("*", [])]:
            handler(event)

        return event

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def events(self) -> List[RuntimeEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
