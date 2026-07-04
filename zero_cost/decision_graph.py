from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class DecisionNode:
    """Deterministic node in the runtime decision graph.

    Nodes describe why the runtime selected a path. They are declarative and
    serializable; they do not execute components or mutate runtime state.
    """

    node_id: str
    kind: str
    label: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node_id,
            "kind": self.kind,
            "label": self.label,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class DecisionEdge:
    """Directed transition between deterministic decision nodes."""

    source: str
    target: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DecisionGraph:
    """Observable decision model for a single zero-cost runtime pass.

    The graph makes the intent -> action -> flow -> execution-plan path explicit
    without coupling components to each other. Interfaces can render this graph,
    but they must not derive runtime logic from it.
    """

    graph_id: str
    nodes: List[DecisionNode]
    edges: List[DecisionEdge]
    selected_path: List[str]
    terminal_node: str
    reason: str = "zero_cost_decision_graph"

    def node_ids(self) -> List[str]:
        return [node.node_id for node in self.nodes]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "selected_path": list(self.selected_path),
            "terminal_node": self.terminal_node,
            "reason": self.reason,
        }


class DecisionGraphEngine:
    """Builds decision graphs from runtime API contracts.

    No LLM. No embeddings. No external service. The engine consumes serialized
    outputs from existing zero-cost components and produces an auditable graph.
    """

    def build(
        self,
        *,
        intent_match: Mapping[str, Any] | object,
        action_plan: Mapping[str, Any] | object,
        execution_flow: Mapping[str, Any] | object,
        execution_plan: Mapping[str, Any] | object,
    ) -> DecisionGraph:
        intent = _as_mapping(intent_match)
        action = _as_mapping(action_plan)
        flow = _as_mapping(execution_flow)
        plan = _as_mapping(execution_plan)

        nodes = [
            DecisionNode(
                node_id="input.intent",
                kind="intent",
                label=str(intent.get("intent", "fallback")),
                payload={
                    "confidence": float(intent.get("confidence", 0.0) or 0.0),
                    "matched_terms": list(_as_iterable(intent.get("matched_terms", []))),
                    "reason": str(intent.get("reason", "unknown")),
                },
            ),
            DecisionNode(
                node_id="plan.action",
                kind="action",
                label=str(action.get("action", "fallback_response")),
                payload={
                    "confidence": float(action.get("confidence", 0.0) or 0.0),
                    "source_intent": str(action.get("source_intent", "fallback")),
                    "payload": dict(_mapping_or_empty(action.get("payload", {}))),
                    "reason": str(action.get("reason", "unknown")),
                },
            ),
            DecisionNode(
                node_id="route.flow",
                kind="flow",
                label=str(flow.get("flow", "fallback")),
                payload={
                    "source_action": str(flow.get("source_action", "fallback_response")),
                    "steps": list(_as_iterable(flow.get("steps", []))),
                    "payload": dict(_mapping_or_empty(flow.get("payload", {}))),
                    "reason": str(flow.get("reason", "unknown")),
                },
            ),
            DecisionNode(
                node_id="execution.plan",
                kind="execution_plan",
                label=str(plan.get("flow", "fallback")),
                payload={
                    "source_action": str(plan.get("source_action", "fallback_response")),
                    "steps": [dict(step) for step in _mapping_items(plan.get("steps", []))],
                    "payload": dict(_mapping_or_empty(plan.get("payload", {}))),
                    "reason": str(plan.get("reason", "unknown")),
                },
            ),
        ]

        edges = [
            DecisionEdge("input.intent", "plan.action", "intent_to_action"),
            DecisionEdge("plan.action", "route.flow", "action_to_flow"),
            DecisionEdge("route.flow", "execution.plan", "flow_to_execution_plan"),
        ]

        selected_path = [node.node_id for node in nodes]
        return DecisionGraph(
            graph_id="runtime.decision_graph.v1",
            nodes=nodes,
            edges=edges,
            selected_path=selected_path,
            terminal_node=selected_path[-1],
        )


def _as_mapping(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        mapped = to_dict()
        if isinstance(mapped, Mapping):
            return mapped
    return {}


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_iterable(value: Any) -> Iterable[Any]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return value
    return []


def _mapping_items(value: Any) -> Iterable[Mapping[str, Any]]:
    for item in _as_iterable(value):
        if isinstance(item, Mapping):
            yield item
