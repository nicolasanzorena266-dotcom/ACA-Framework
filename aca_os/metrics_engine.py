from __future__ import annotations

import json
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Dict, Iterable, List, Mapping

from aca_os.execution_trace import ExecutionTrace, TraceEvent, sanitize


@dataclass(frozen=True)
class CounterMetric:
    name: str
    value: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": self.value, "type": "counter"}


@dataclass(frozen=True)
class GaugeMetric:
    name: str
    value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": self.value, "type": "gauge"}


@dataclass(frozen=True)
class HistogramMetric:
    name: str
    count: int = 0
    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": "histogram",
            "count": self.count,
            "min": self.min,
            "max": self.max,
            "avg": self.avg,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
        }


@dataclass(frozen=True)
class ComponentMetrics:
    component: str
    event_count: int
    operations: List[str] = field(default_factory=list)
    duration_ms: HistogramMetric = field(default_factory=lambda: HistogramMetric("component.duration_ms"))
    success_count: int = 0
    error_count: int = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.error_count
        if total == 0:
            return 1.0
        return round(self.success_count / total, 6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "event_count": self.event_count,
            "operations": list(self.operations),
            "duration_ms": self.duration_ms.to_dict(),
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
        }


@dataclass(frozen=True)
class RuntimeMetricsSnapshot:
    runtime_id: str
    trace_count: int
    process_count: int
    event_count: int
    operation_count: int
    total_duration_ms: HistogramMetric
    components: Dict[str, ComponentMetrics] = field(default_factory=dict)
    counters: Dict[str, CounterMetric] = field(default_factory=dict)
    gauges: Dict[str, GaugeMetric] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "trace_count": self.trace_count,
            "process_count": self.process_count,
            "event_count": self.event_count,
            "operation_count": self.operation_count,
            "total_duration_ms": self.total_duration_ms.to_dict(),
            "components": {
                name: metrics.to_dict() for name, metrics in sorted(self.components.items())
            },
            "counters": {name: metric.to_dict() for name, metric in sorted(self.counters.items())},
            "gauges": {name: metric.to_dict() for name, metric in sorted(self.gauges.items())},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class MetricsEngine:
    """Deterministic metrics service derived from Execution Trace.

    The engine is deliberately passive: components do not call each other and UI
    layers never compute metrics. Execution Trace remains the source of truth;
    this service only aggregates it into a stable metrics contract.
    """

    def __init__(self) -> None:
        self._traces: Dict[str, ExecutionTrace] = {}
        self._manual_counters: Dict[str, int] = {}
        self._manual_gauges: Dict[str, float] = {}

    def observe_trace(self, trace: ExecutionTrace) -> None:
        self._traces[trace.trace_id] = trace

    def increment(self, name: str, value: int = 1) -> None:
        self._manual_counters[name] = self._manual_counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self._manual_gauges[name] = float(value)

    def snapshot(self, *, runtime_id: str = "runtime") -> RuntimeMetricsSnapshot:
        traces = list(self._traces.values())
        trace_events = [event for trace in traces for event in trace.events]
        components = _component_metrics(trace_events)

        counters = {
            "runtime.trace_count": CounterMetric("runtime.trace_count", len(traces)),
            "runtime.event_count": CounterMetric("runtime.event_count", len(trace_events)),
            "runtime.process_count": CounterMetric("runtime.process_count", len(traces)),
        }
        counters.update(
            {name: CounterMetric(name, value) for name, value in self._manual_counters.items()}
        )

        gauges = {
            "runtime.last_trace_duration_ms": GaugeMetric(
                "runtime.last_trace_duration_ms",
                traces[-1].duration_ms if traces else 0.0,
            )
        }
        gauges.update({name: GaugeMetric(name, value) for name, value in self._manual_gauges.items()})

        return RuntimeMetricsSnapshot(
            runtime_id=runtime_id,
            trace_count=len(traces),
            process_count=len(traces),
            event_count=len(trace_events),
            operation_count=len({event.operation for event in trace_events}),
            total_duration_ms=_histogram(
                "runtime.process.duration_ms", [trace.duration_ms for trace in traces]
            ),
            components=components,
            counters=counters,
            gauges=gauges,
        )

    def export(self, *, runtime_id: str = "runtime", format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot(runtime_id=runtime_id)
        if format == "dict":
            return snapshot.to_dict()
        if format == "json":
            return snapshot.to_json()
        raise ValueError(f"Unsupported metrics export format: {format}")


def build_metrics_from_trace(trace: ExecutionTrace, *, runtime_id: str | None = None) -> RuntimeMetricsSnapshot:
    engine = MetricsEngine()
    engine.observe_trace(trace)
    return engine.snapshot(runtime_id=runtime_id or trace.runtime_id)


def _component_metrics(events: Iterable[TraceEvent]) -> Dict[str, ComponentMetrics]:
    grouped: Dict[str, List[TraceEvent]] = {}
    for event in events:
        grouped.setdefault(event.component, []).append(event)

    output: Dict[str, ComponentMetrics] = {}
    for component, items in grouped.items():
        error_count = sum(1 for item in items if _is_error(item))
        success_count = len(items) - error_count
        output[component] = ComponentMetrics(
            component=component,
            event_count=len(items),
            operations=sorted({item.operation for item in items}),
            duration_ms=_histogram(
                f"component.{component}.duration_ms", [item.duration_ms for item in items]
            ),
            success_count=success_count,
            error_count=error_count,
        )
    return output


def _is_error(event: TraceEvent) -> bool:
    values = [event.operation, event.component, event.output, event.metadata]
    rendered = str(sanitize(values)).lower()
    return "error" in rendered or "exception" in rendered or "failed" in rendered


def _histogram(name: str, values: Iterable[float]) -> HistogramMetric:
    clean = sorted(float(value or 0.0) for value in values)
    if not clean:
        return HistogramMetric(name=name)
    return HistogramMetric(
        name=name,
        count=len(clean),
        min=round(clean[0], 3),
        max=round(clean[-1], 3),
        avg=round(mean(clean), 3),
        p50=round(_percentile(clean, 50), 3),
        p95=round(_percentile(clean, 95), 3),
        p99=round(_percentile(clean, 99), 3),
    )


def _percentile(sorted_values: List[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
