from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Protocol

from aca_os.execution_trace import sanitize


class DemoRequester(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | str | None = None,
        body: Mapping[str, Any] | bytes | str | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class HumanDemoStep:
    """One deterministic human-facing demo action."""

    id: str
    title: str
    message: str
    expected_decision: str | None = None
    expected_tool_key: str | None = None
    purpose: str = "runtime_smoke"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "expected_decision": self.expected_decision,
            "expected_tool_key": self.expected_tool_key,
            "purpose": self.purpose,
        }


DEFAULT_HUMAN_DEMO_STEPS: tuple[HumanDemoStep, ...] = (
    HumanDemoStep(
        id="concept-cleas",
        title="Domain concept lookup",
        message="Que es CLEAS?",
        expected_decision="USE_TOOL",
        expected_tool_key="cleas",
        purpose="Show domain lookup with trace and evidence.",
    ),
    HumanDemoStep(
        id="human-escalation",
        title="Policy escalation",
        message="Necesito hablar con un asesor",
        expected_decision="ESCALATE",
        purpose="Show deterministic policy short-circuit for human escalation.",
    ),
    HumanDemoStep(
        id="concept-franquicia",
        title="Second concept lookup",
        message="Que es la franquicia?",
        expected_decision="USE_TOOL",
        expected_tool_key="franquicia",
        purpose="Show repeatable Runtime behavior across multiple inputs.",
    ),
)


@dataclass(frozen=True)
class HumanDemoScenario:
    """Stable scenario contract for manual ACA validation."""

    id: str = "aca-human-test-demo"
    title: str = "ACA Human Test Demo"
    description: str = "Deterministic end-to-end demo for a human tester using Runtime APIs only."
    steps: tuple[HumanDemoStep, ...] = DEFAULT_HUMAN_DEMO_STEPS

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": "human_test_demo_scenario.v1",
                "id": self.id,
                "title": self.title,
                "description": self.description,
                "step_count": len(self.steps),
                "steps": [step.to_dict() for step in self.steps],
                "rules": {
                    "business_logic": "runtime_only",
                    "interfaces": "request_response_only",
                    "external_ai_required": False,
                    "network_required": False,
                },
            }
        )


@dataclass(frozen=True)
class HumanDemoRun:
    """Result of one human-test demo execution."""

    scenario: Dict[str, Any]
    status: str
    health: Dict[str, Any]
    runtime_status: Dict[str, Any]
    steps: list[Dict[str, Any]] = field(default_factory=list)
    final_metrics: Dict[str, Any] = field(default_factory=dict)
    studio_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": "human_test_demo_run.v1",
                "status": self.status,
                "scenario": self.scenario,
                "health": self.health,
                "runtime_status": self.runtime_status,
                "steps": self.steps,
                "final_metrics": self.final_metrics,
                "studio_state": self.studio_state,
                "metadata": self.metadata,
            }
        )


class HumanTestDemoRunner:
    """Runs a human demo through the Runtime Interface boundary.

    The runner is intentionally dumb: it sends requests, validates stable output
    shape, and summarizes what the Runtime returned. It never reaches into
    Runtime components and owns no domain behavior.
    """

    def __init__(self, requester: DemoRequester, scenario: HumanDemoScenario | None = None) -> None:
        self.requester = requester
        self.scenario = scenario or HumanDemoScenario()

    def scenario_contract(self) -> Dict[str, Any]:
        return self.scenario.to_dict()

    def run(
        self,
        *,
        conversation_id: str = "human-demo",
        memory_path: str | None = None,
    ) -> Dict[str, Any]:
        health = self._request("GET", "/health", query=_query(memory_path))
        runtime_status = self._request("GET", "/runtime/status", query=_query(memory_path))
        step_results = [
            self._run_step(step, conversation_id=conversation_id, memory_path=memory_path)
            for step in self.scenario.steps
        ]
        final_metrics = self._request("GET", "/runtime/metrics", query=_query(memory_path))
        studio_state = self._request("GET", "/studio/state", query=_query(memory_path))
        status = "passed" if all(step["status"] == "passed" for step in step_results) else "failed"
        return HumanDemoRun(
            scenario=self.scenario_contract(),
            status=status,
            health=health,
            runtime_status=runtime_status,
            steps=step_results,
            final_metrics=final_metrics,
            studio_state=studio_state,
            metadata={
                "conversation_id": conversation_id,
                "source": "runtime_api",
                "business_logic": "runtime_only",
                "human_readable": True,
            },
        ).to_dict()

    def run_markdown(self, *, conversation_id: str = "human-demo", memory_path: str | None = None) -> str:
        report = self.run(conversation_id=conversation_id, memory_path=memory_path)
        lines = [
            f"# {report['scenario']['title']}",
            "",
            f"Status: {report['status']}",
            f"Runtime: {report['runtime_status']['runtime_id']} ({report['runtime_status']['status']})",
            f"Components: {report['runtime_status']['component_count']}",
            f"Plugins: {report['runtime_status']['plugin_count']}",
            "",
            "## Steps",
        ]
        for step in report["steps"]:
            lines.extend(
                [
                    f"- {step['id']}: {step['status']}",
                    f"  input: {step['input']}",
                    f"  decision: {step['decision']}",
                    f"  response: {step['response_preview']}",
                ]
            )
        lines.extend(
            [
                "",
                "## Validation",
                f"Trace events observed: {sum(step['trace_event_count'] for step in report['steps'])}",
                "Business logic: runtime_only",
            ]
        )
        return "\n".join(lines) + "\n"

    def _run_step(
        self,
        step: HumanDemoStep,
        *,
        conversation_id: str,
        memory_path: str | None,
    ) -> Dict[str, Any]:
        output = self._request(
            "POST",
            "/runtime/events",
            body={
                "event_type": "user_message",
                "payload": step.message,
                "metadata": {"conversation_id": conversation_id, "demo_step": step.id},
                "memory_path": memory_path,
                "include_trace": True,
                "include_introspection": True,
                "include_studio": True,
            },
        )
        policy = output.get("policy_result") or {}
        trace = output.get("execution_trace") or {}
        introspection = output.get("introspection") or {}
        studio = output.get("studio") or {}
        response = str(output.get("response") or "")
        failures = []
        if output.get("conversation_id") != conversation_id:
            failures.append("conversation_id_mismatch")
        if not response:
            failures.append("missing_response")
        if not trace.get("trace_id"):
            failures.append("missing_trace")
        if step.expected_decision and policy.get("decision") != step.expected_decision:
            failures.append("unexpected_policy_decision")
        if step.expected_tool_key and policy.get("tool_key") != step.expected_tool_key:
            failures.append("unexpected_tool_key")
        return sanitize(
            {
                "id": step.id,
                "title": step.title,
                "status": "failed" if failures else "passed",
                "failures": failures,
                "input": step.message,
                "decision": policy.get("decision"),
                "tool_key": policy.get("tool_key"),
                "response_preview": response[:160],
                "trace_id": trace.get("trace_id"),
                "trace_event_count": len(trace.get("events") or []),
                "introspection_status": introspection.get("status"),
                "studio_status": studio.get("status"),
                "raw_output_keys": sorted(output.keys()),
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | str | None = None,
        body: Mapping[str, Any] | bytes | str | None = None,
    ) -> Dict[str, Any]:
        response = self.requester(method, path, query=query, body=body)
        status_code = getattr(response, "status_code", 200)
        payload = getattr(response, "payload", response)
        if int(status_code) >= 400:
            message = payload.get("error", {}).get("message") if isinstance(payload, Mapping) else None
            raise ValueError(message or f"Demo request failed: {method} {path}.")
        if not isinstance(payload, Mapping):
            raise ValueError(f"Demo request returned non-object payload for {method} {path}.")
        return sanitize(dict(payload))


def _query(memory_path: str | None) -> Dict[str, str] | None:
    return {"memory_path": memory_path} if memory_path else None
