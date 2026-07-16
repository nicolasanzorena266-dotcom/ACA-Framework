from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AUTHORITY_GRAPH_CONTRACT = "authority_dependency_graph.v1"
AUTHORITY_GRAPH_VERSION = "sa-3.1"


@dataclass(frozen=True)
class _CallSite:
    file: str
    function: str
    line: int
    call: str
    expression: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "function": self.function,
            "line": self.line,
            "call": self.call,
            "expression": self.expression,
        }


@dataclass(frozen=True)
class _DefinitionSite:
    file: str
    function: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "function": self.function,
            "line": self.line,
        }


@dataclass(frozen=True)
class _TextRead:
    file: str
    function: str
    line: int
    source_kind: str
    expression: str
    source_line: str


@dataclass(frozen=True)
class _TransitionSpec:
    call_suffix: str
    source: str
    target: str
    producer: str
    consumer: str
    dependency_type: str
    authority: str
    mutability: str


@dataclass(frozen=True)
class _DefinitionTransitionSpec:
    function: str
    source: str
    target: str
    producer: str
    consumer: str
    dependency_type: str
    authority: str
    mutability: str


@dataclass
class AuthorityDependencyGraph:
    repository_root: Path
    source_hash: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    semantic_firewall_audit: list[dict[str, Any]]
    recomputation_audit: list[dict[str, Any]]
    dependency_cycles: list[dict[str, Any]]
    promotion_readiness: list[dict[str, Any]]
    promotion_order: list[dict[str, Any]]
    runtime_observation: dict[str, Any]
    report: dict[str, Any]
    graph_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": AUTHORITY_GRAPH_CONTRACT,
            "version": AUTHORITY_GRAPH_VERSION,
            "repository_root": str(self.repository_root),
            "source_hash": self.source_hash,
            "graph_hash": self.graph_hash,
            "nodes": [dict(item) for item in self.nodes],
            "edges": [dict(item) for item in self.edges],
            "semantic_firewall_audit": [dict(item) for item in self.semantic_firewall_audit],
            "recomputation_audit": [dict(item) for item in self.recomputation_audit],
            "dependency_cycles": [dict(item) for item in self.dependency_cycles],
            "promotion_readiness": [dict(item) for item in self.promotion_readiness],
            "promotion_order": [dict(item) for item in self.promotion_order],
            "runtime_observation": dict(self.runtime_observation),
            "report": dict(self.report),
        }

    def inspect_artifact(self, artifact_id: str) -> dict[str, Any]:
        node = next((item for item in self.nodes if item["id"] == artifact_id), None)
        if node is None:
            raise KeyError(f"Unknown authority artifact: {artifact_id}")
        return {
            "contract": "authority_artifact_inspection.v1",
            "artifact": dict(node),
            "producers": [
                dict(edge) for edge in self.edges if edge["target"] == artifact_id
            ],
            "consumers": [
                dict(edge) for edge in self.edges if edge["source"] == artifact_id
            ],
            "recomputations": [
                dict(item)
                for item in self.recomputation_audit
                if item["artifact"] == artifact_id
            ],
            "semantic_firewall_violations": [
                dict(item)
                for item in self.semantic_firewall_audit
                if item["artifact"] == artifact_id and item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
            ],
            "promotion_readiness": next(
                (
                    dict(item)
                    for item in self.promotion_readiness
                    if item["artifact"] == artifact_id
                ),
                {},
            ),
        }

    def to_mermaid(self) -> str:
        readiness = {
            item["artifact"]: item["status"] for item in self.promotion_readiness
        }
        lines = ["flowchart TD"]
        for node in self.nodes:
            node_id = _mermaid_id(node["id"])
            label = str(node["label"]).replace('"', "'")
            lines.append(f'    {node_id}["{label}"]')
        for edge in self.edges:
            source = _mermaid_id(edge["source"])
            target = _mermaid_id(edge["target"])
            label = f"{edge['producer']} / {edge['authority']}".replace('"', "'")
            lines.append(f'    {source} -->|"{label}"| {target}')
        lines.extend(
            [
                "    classDef ready fill:#d7f5df,stroke:#247a3c,color:#102816",
                "    classDef low fill:#e8f3ff,stroke:#2d6fa3,color:#10202d",
                "    classDef medium fill:#fff2c7,stroke:#9b7412,color:#322400",
                "    classDef high fill:#ffe2bd,stroke:#a45b00,color:#351d00",
                "    classDef blocked fill:#ffd9d9,stroke:#a62929,color:#351010",
            ]
        )
        class_groups = {
            "READY": "ready",
            "LOW_RISK": "low",
            "MEDIUM_RISK": "medium",
            "HIGH_RISK": "high",
            "BLOCKED": "blocked",
        }
        for status, class_name in class_groups.items():
            members = [
                _mermaid_id(node["id"])
                for node in self.nodes
                if readiness.get(node["id"]) == status
            ]
            if members:
                lines.append(f"    class {','.join(members)} {class_name}")
        return "\n".join(lines)


_AUTHORITY_FILES = (
    "aca_os/conversation_manager.py",
    "aca_os/conversation_state.py",
    "aca_os/semantic_authority.py",
    "aca_os/semantic_projection.py",
    "aca_os/semantic_authority_pilot.py",
    "aca_os/runtime.py",
    "aca_os/mission_manager.py",
    "aca_os/policy_manager.py",
    "aca_os/runtime_executor.py",
    "aca_os/tool_engine.py",
    "aca_os/legacy_runtime_executor.py",
    "aca_os/execution_authority.py",
    "aca_os/step_handlers.py",
    "aca_os/narrative_response_composer.py",
    "aca_os/llm_verbalization.py",
    "aca_os/operational_work_mapper.py",
    "aca_os/operational_governance_gate.py",
    "aca_os/operational_audit_ledger.py",
    "aca_os/runtime_timeline.py",
    "aca_os/session.py",
    "zero_cost/intent_matcher.py",
    "zero_cost/action_planner.py",
    "zero_cost/flow_router.py",
    "zero_cost/execution_plan.py",
    "zero_cost/decision_graph.py",
    "kernel/aca_kernel/compiler/compiler.py",
    "kernel/aca_kernel/core/kernel.py",
    "kernel/aca_kernel/operations/basic.py",
    "plugins/galicia.insurance/semantic.py",
    "plugins/generic.open_chat/semantic.py",
)


def _node(
    label: str,
    owner: str,
    classifications: list[str],
    mutable: bool,
    side_effects: bool,
    promotion_candidate: bool = False,
    never_promote_reason: str = "",
) -> dict[str, Any]:
    return {
        "label": label,
        "owner": owner,
        "classifications": classifications,
        "mutable": mutable,
        "side_effects": side_effects,
        "promotion_candidate": promotion_candidate,
        "never_promote_reason": never_promote_reason,
    }


_NODE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "user_text": _node("User text", "transport", ["PRIMARY_AUTHORITY", "TEXT_DEPENDENT"], False, False, False, "User text is the source input, not a promotion target."),
    "semantic_representation": _node("SemanticRepresentation", "semantic_authority", ["DERIVED", "SHADOW"], False, False),
    "semantic_projection": _node("SemanticProjection", "semantic_projector", ["DERIVED", "SHADOW"], False, False),
    "conversation_state": _node("ConversationState", "conversation_manager", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False, False, "ConversationState remains the state owner and cannot be replaced by a turn projection."),
    "conversational_act": _node("ConversationalAct", "semantic_pilot_or_legacy", ["DERIVED", "PRIMARY_AUTHORITY"], True, False, True),
    "slot_state": _node("Slots", "conversation_state", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False, True),
    "conversation_facts": _node("Conversation facts", "conversation_state", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False, True),
    "topic_state": _node("Topic stack", "conversation_state", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False, True),
    "conversational_goal": _node("Conversational goal", "semantic_pilot_or_legacy", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False, True),
    "conversation_intent_model": _node("ConversationIntentModel", "conversation_state", ["DERIVED", "STATE_DEPENDENT"], True, False, True),
    "information_gain_plan": _node("InformationGainPlan", "conversation_state", ["DERIVED", "STATE_DEPENDENT"], True, False, False, "Planner output must remain derived from its authoritative inputs."),
    "conversation_plan": _node("ConversationPlan", "conversation_state", ["DERIVED", "STATE_DEPENDENT"], True, False, False, "Planner output must remain derived from its authoritative inputs."),
    "conversation_response_plan": _node("ConversationResponsePlan", "conversation_state", ["DERIVED", "STATE_DEPENDENT"], True, False, False, "Response planning is derived and must not become semantic authority."),
    "cognitive_state": _node("CognitiveState", "runtime", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False),
    "intent_match": _node("IntentMatch", "intent_matcher", ["PRIMARY_AUTHORITY", "TEXT_DEPENDENT"], True, False, True),
    "action_plan": _node("ActionPlan", "action_planner", ["DERIVED"], False, False, False, "ActionPlan is an operational derivation, not a semantic projection target."),
    "execution_flow": _node("ExecutionFlow", "flow_router", ["DERIVED"], False, False, False, "Flow routing must inherit authority from ActionPlan."),
    "execution_plan": _node("ExecutionPlan", "execution_plan", ["DERIVED"], False, False, False, "ExecutionPlan must remain an executable derivation."),
    "decision_graph": _node("DecisionGraph", "decision_graph_engine", ["DERIVED"], False, False, False, "DecisionGraph is explanatory output."),
    "mission": _node("Mission", "mission_manager", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, False, False, "MissionManager must consume semantics but retain mission authority."),
    "policy_result": _node("PolicyResult", "policy_manager", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], False, True, False, "Safety authority must remain independent from semantic authority."),
    "kernel_program": _node("Kernel program", "graph_compiler", ["DERIVED", "TEXT_DEPENDENT"], False, False, False, "Kernel program selection must remain derived from authoritative routing."),
    "kernel_entities": _node("Kernel entities", "kernel_extract", ["DERIVED", "STATE_DEPENDENT"], True, False, True),
    "kernel_hypotheses": _node("Kernel hypotheses", "kernel_infer", ["DERIVED", "STATE_DEPENDENT"], True, False, False, "Hypotheses require their own revision authority."),
    "kernel_plan": _node("Kernel plan", "kernel_plan", ["DERIVED", "STATE_DEPENDENT"], True, False, False, "Kernel plan must inherit upstream authority."),
    "context_bundle": _node("ContextBundle", "context_manager", ["DERIVED", "STATE_DEPENDENT"], False, False, False, "ContextBundle is a view, not an authority."),
    "runtime_outcomes": _node("Runtime outcomes", "runtime_executor", ["DERIVED", "STATE_DEPENDENT"], True, True, False, "Execution outcomes can only be authoritative after execution."),
    "tool_execution": _node("Tool execution", "tool_engine", ["PRIMARY_AUTHORITY", "STATE_DEPENDENT"], True, True, False, "Tool execution authority cannot be delegated to semantics."),
    "deterministic_response": _node("Deterministic response", "kernel", ["DERIVED", "OUTPUT_ONLY"], True, False, False, "Response text is output, not semantic authority."),
    "narrative_response": _node("Narrative response", "narrative_response_composer", ["DERIVED", "OUTPUT_ONLY"], True, False, False, "Narrative composition is output-only."),
    "verbalized_response": _node("Verbalized response", "llm_verbalizer", ["DERIVED", "OUTPUT_ONLY"], True, False, False, "The LLM is never an authority source."),
    "conversation_fulfillment": _node("ConversationFulfillment", "conversation_state", ["DERIVED", "STATE_DEPENDENT"], True, False, False, "Fulfillment is post-response evaluation."),
    "candidate_work": _node("Candidate Work", "operational_work_mapper", ["DERIVED", "SHADOW"], False, False, False, "Candidate Work remains a passive operational projection."),
    "case_state_projection": _node("Case State Projection", "operational_work_mapper", ["DERIVED", "SHADOW"], False, False, False, "Case state is a reconstructable view."),
    "governance_assessment": _node("Governance assessment", "operational_governance_gate", ["DERIVED", "SHADOW"], False, True, False, "Governance must remain an independent execution gate."),
    "operational_ledger": _node("Operational Audit Ledger", "operational_audit_ledger", ["DERIVED", "SHADOW"], True, True, False, "The ledger records authority; it never receives semantic authority."),
}


_TRANSITIONS = (
    _TransitionSpec("semantic_authority.interpret", "user_text", "semantic_representation", "semantic_authority", "semantic_authority", "interpretation", "semantic_shadow", "immutable"),
    _TransitionSpec("semantic_projector.project", "semantic_representation", "semantic_projection", "semantic_projector", "semantic_projector", "projection", "semantic_shadow", "immutable"),
    _TransitionSpec("recognize_conversational_act", "user_text", "conversational_act", "conversation_state", "conversation_manager", "legacy_interpretation", "legacy_primary", "state_replacement"),
    _TransitionSpec("select_conversational_act_authority", "semantic_projection", "conversational_act", "semantic_authority_pilot", "conversation_manager", "atomic_authority_selection", "semantic_conditional", "atomic_replacement"),
    _TransitionSpec("resolve_pending_slot_answers", "user_text", "slot_state", "conversation_state", "conversation_manager", "legacy_interpretation", "legacy_primary", "persistent_state_update"),
    _TransitionSpec("assimilate_user_facts", "user_text", "conversation_facts", "conversation_state", "conversation_manager", "legacy_interpretation", "legacy_primary", "persistent_state_update"),
    _TransitionSpec("update_topic_stack", "user_text", "topic_state", "conversation_state", "conversation_manager", "legacy_interpretation", "legacy_primary", "persistent_state_update"),
    _TransitionSpec("apply_conversational_goal", "user_text", "conversational_goal", "conversation_state", "conversation_manager", "legacy_interpretation", "legacy_primary", "state_replacement"),
    _TransitionSpec("select_conversational_goal_authority", "semantic_projection", "conversational_goal", "semantic_authority_pilot", "conversation_manager", "atomic_authority_selection", "semantic_conditional", "atomic_replacement"),
    _TransitionSpec("model_conversational_intent", "conversation_state", "conversation_intent_model", "conversation_state", "conversation_manager_or_runtime", "legacy_recomputation", "legacy_recomputed", "state_replacement"),
    _TransitionSpec("plan_information_gain", "conversation_intent_model", "information_gain_plan", "conversation_state", "conversation_manager_or_runtime", "legacy_recomputation", "legacy_recomputed", "state_replacement"),
    _TransitionSpec("plan_conversation", "information_gain_plan", "conversation_plan", "conversation_state", "conversation_manager_or_runtime", "legacy_recomputation", "legacy_recomputed", "state_replacement"),
    _TransitionSpec("plan_conversational_response", "conversation_plan", "conversation_response_plan", "conversation_state", "conversation_manager_or_runtime", "legacy_recomputation", "legacy_recomputed", "state_replacement"),
    _TransitionSpec("to_cognitive_state", "conversation_state", "cognitive_state", "conversation_state", "runtime", "state_projection", "inherited", "state_replacement"),
    _TransitionSpec("project_from_cognitive_state", "cognitive_state", "conversation_state", "conversation_manager", "runtime", "state_projection", "inherited", "persistent_state_merge"),
    _TransitionSpec("intent_matcher.match", "user_text", "intent_match", "intent_matcher", "runtime", "legacy_interpretation", "legacy_primary", "state_replacement"),
    _TransitionSpec("_intent_from_conversation_act", "conversational_act", "intent_match", "runtime", "runtime", "post_match_override", "shared", "state_replacement"),
    _TransitionSpec("_intent_from_slot_resolution", "slot_state", "intent_match", "runtime", "runtime", "post_match_override", "shared", "state_replacement"),
    _TransitionSpec("action_planner.plan", "intent_match", "action_plan", "action_planner", "runtime", "planning", "inherited", "immutable"),
    _TransitionSpec("flow_router.route", "action_plan", "execution_flow", "flow_router", "runtime", "routing", "inherited", "immutable"),
    _TransitionSpec("ExecutionPlan.from_flow", "execution_flow", "execution_plan", "execution_plan", "runtime", "compilation", "inherited", "immutable"),
    _TransitionSpec("decision_graph_engine.build", "execution_plan", "decision_graph", "decision_graph_engine", "runtime", "explanation_projection", "inherited", "immutable"),
    _TransitionSpec("mission_manager.before_kernel", "execution_plan", "mission", "mission_manager", "runtime", "mission_selection", "legacy_primary", "persistent_state_update"),
    _TransitionSpec("policy_manager.evaluate", "execution_plan", "policy_result", "policy_manager", "policy_step_handler", "safety_decision", "independent_primary", "immutable"),
    _TransitionSpec("RuntimeExecutor.execute", "execution_plan", "runtime_outcomes", "runtime_executor", "runtime", "official_execution", "execution_primary", "state_and_side_effects"),
    _TransitionSpec("legacy_runtime.execute", "execution_plan", "runtime_outcomes", "legacy_runtime_executor", "runtime", "legacy_execution", "legacy_or_validation", "state_and_side_effects"),
    _TransitionSpec("compiler.compile", "user_text", "kernel_program", "graph_compiler", "runtime_or_kernel_handler", "program_selection", "legacy_primary", "immutable"),
    _TransitionSpec("kernel.run", "kernel_program", "cognitive_state", "kernel", "kernel_step_handler", "cognitive_execution", "inherited", "state_replacement"),
    _TransitionSpec("memory_engine.consolidate", "cognitive_state", "cognitive_state", "memory_engine", "memory_step_handler", "memory_consolidation", "inherited", "state_replacement"),
    _TransitionSpec("context_manager.build", "conversation_state", "context_bundle", "context_manager", "context_step_handler", "context_projection", "inherited", "immutable"),
    _TransitionSpec("tool_engine.execute", "execution_plan", "tool_execution", "tool_engine", "tool_lookup_step_handler", "tool_execution", "execution_primary", "state_and_side_effects"),
    _TransitionSpec("NarrativeResponseComposer.compose", "deterministic_response", "narrative_response", "narrative_response_composer", "output_step_handler", "output_realization", "output_transform", "state_replacement"),
    _TransitionSpec("llm_verbalizer.verbalize", "narrative_response", "verbalized_response", "llm_verbalizer", "output_step_handler", "output_realization", "output_transform", "state_replacement"),
    _TransitionSpec("evaluate_conversational_goal_fulfillment", "verbalized_response", "conversation_fulfillment", "conversation_state", "conversation_manager", "post_response_evaluation", "inherited", "state_replacement"),
)


_GUARDED_MULTI_AUTHORITY_ARTIFACTS = ("conversational_act", "conversational_goal")


_DEFINITION_TRANSITIONS = (
    _DefinitionTransitionSpec("Extract.execute", "user_text", "kernel_entities", "kernel_extract", "kernel", "legacy_interpretation", "legacy_primary", "state_replacement"),
    _DefinitionTransitionSpec("Infer.execute", "kernel_entities", "kernel_hypotheses", "kernel_infer", "kernel", "cognitive_inference", "inherited", "state_replacement"),
    _DefinitionTransitionSpec("Plan.execute", "kernel_hypotheses", "kernel_plan", "kernel_plan", "kernel", "cognitive_planning", "inherited", "state_replacement"),
    _DefinitionTransitionSpec("Generate.execute", "kernel_plan", "deterministic_response", "kernel_generate", "kernel", "deterministic_generation", "inherited", "state_replacement"),
    _DefinitionTransitionSpec("map_operational_work", "conversation_state", "candidate_work", "operational_work_mapper", "evaluation_shadow", "shadow_projection", "shadow", "immutable"),
    _DefinitionTransitionSpec("_case_state_projection", "candidate_work", "case_state_projection", "operational_work_mapper", "candidate_ranking_shadow", "shadow_projection", "shadow", "immutable"),
    _DefinitionTransitionSpec("assess_operational_governance", "candidate_work", "governance_assessment", "operational_governance_gate", "evaluation_shadow", "shadow_governance", "independent_shadow", "immutable"),
    _DefinitionTransitionSpec("project_operational_audit_ledger", "governance_assessment", "operational_ledger", "operational_audit_ledger", "evaluation_or_tool_integration", "audit_projection", "independent_shadow", "append_only_projection"),
)


_TRACE_OPERATION_ARTIFACTS = {
    "SEMANTIC_REPRESENTATION_SHADOW": "semantic_representation",
    "SEMANTIC_PROJECTION_SHADOW": "semantic_projection",
    "SEMANTIC_AUTHORITY_VERTICAL_PILOT": "conversational_act",
    "INTENT_MATCH": "intent_match",
    "ACTION_PLAN": "action_plan",
    "FLOW_ROUTE": "execution_flow",
    "EXECUTION_PLAN": "execution_plan",
    "MISSION_CREATE": "mission",
    "MISSION_UPDATE": "mission",
    "POLICY_RESULT": "policy_result",
    "KERNEL_RUN": "cognitive_state",
    "NARRATIVE_RESPONSE_COMPOSE": "narrative_response",
    "LLM_VERBALIZE": "verbalized_response",
    "CONVERSATION_FULFILLMENT": "conversation_fulfillment",
}


def build_authority_dependency_graph(
    repository_root: str | Path | None = None,
    *,
    runtime_trace: Mapping[str, Any] | None = None,
) -> AuthorityDependencyGraph:
    root = Path(repository_root or Path(__file__).resolve().parents[1]).resolve()
    index = _scan_sources(root)
    firewall = _semantic_firewall_audit(index["text_reads"], index["calls"])
    edges = _build_edges(index, firewall)
    recomputations = _recomputation_audit(edges)
    cycles = _find_dependency_cycles(_NODE_BLUEPRINTS, edges)
    nodes = _build_nodes(edges, firewall, recomputations)
    readiness = _promotion_readiness(nodes, edges, firewall, recomputations)
    readiness_by_artifact = {item["artifact"]: item for item in readiness}
    for node in nodes:
        node["promotion_readiness"] = readiness_by_artifact[node["id"]]["status"]
        node["promotion_reason"] = readiness_by_artifact[node["id"]]["reason"]
    promotion_order = _promotion_order(readiness)
    observation = _runtime_observation(runtime_trace)
    report = _build_report(nodes, edges, firewall, recomputations, cycles, readiness, promotion_order)
    graph_payload = {
        "nodes": nodes,
        "edges": edges,
        "semantic_firewall_audit": firewall,
        "recomputation_audit": recomputations,
        "dependency_cycles": cycles,
        "promotion_readiness": readiness,
        "promotion_order": promotion_order,
    }
    return AuthorityDependencyGraph(
        repository_root=root,
        source_hash=index["source_hash"],
        nodes=nodes,
        edges=edges,
        semantic_firewall_audit=firewall,
        recomputation_audit=recomputations,
        dependency_cycles=cycles,
        promotion_readiness=readiness,
        promotion_order=promotion_order,
        runtime_observation=observation,
        report=report,
        graph_hash=_stable_hash(graph_payload),
    )


class _SourceVisitor(ast.NodeVisitor):
    def __init__(self, *, file: str, lines: Sequence[str]) -> None:
        self.file = file
        self.lines = lines
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.parameter_stack: list[set[str]] = []
        self.calls: list[_CallSite] = []
        self.definitions: list[_DefinitionSite] = []
        self.text_reads: list[_TextRead] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        parameters = {
            argument.arg
            for argument in (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
            )
        }
        if node.args.vararg:
            parameters.add(node.args.vararg.arg)
        if node.args.kwarg:
            parameters.add(node.args.kwarg.arg)
        self.parameter_stack.append(parameters)
        self.definitions.append(
            _DefinitionSite(
                file=self.file,
                function=self._qualified_function(),
                line=node.lineno,
            )
        )
        self.generic_visit(node)
        self.parameter_stack.pop()
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        call_name = _call_name(node.func)
        self.calls.append(
            _CallSite(
                file=self.file,
                function=self._qualified_function(),
                line=node.lineno,
                call=call_name,
                expression=_safe_unparse(node),
            )
        )
        if call_name.endswith(".get") or call_name == "get":
            if node.args and _string_constant(node.args[0]) == "last_raw_payload":
                self._record_text_read(node, "last_raw_payload")
        if call_name.endswith("normalize_text") and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Name) and self.parameter_stack:
                if argument.id in self.parameter_stack[-1] and argument.id in {
                    "message",
                    "text",
                    "payload",
                    "source_text",
                } and _is_authoritative_free_text_parameter(self.file, self._qualified_function()):
                    self._record_text_read(argument, "free_text_parameter")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr == "payload" and _root_name(node.value) == "event":
            self._record_text_read(node, "event.payload")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if _string_constant(node.slice) == "last_raw_payload":
            self._record_text_read(node, "last_raw_payload")
        self.generic_visit(node)

    def _record_text_read(self, node: ast.AST, source_kind: str) -> None:
        line = int(getattr(node, "lineno", 0) or 0)
        source_line = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.text_reads.append(
            _TextRead(
                file=self.file,
                function=self._qualified_function(),
                line=line,
                source_kind=source_kind,
                expression=_safe_unparse(node),
                source_line=source_line,
            )
        )

    def _qualified_function(self) -> str:
        parts = self.class_stack + self.function_stack
        return ".".join(parts) if parts else "<module>"


def _scan_sources(root: Path) -> dict[str, Any]:
    calls: list[_CallSite] = []
    definitions: list[_DefinitionSite] = []
    text_reads: list[_TextRead] = []
    source_parts: list[tuple[str, str]] = []
    for relative in _AUTHORITY_FILES:
        path = root / relative
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        source_parts.append((relative, source))
        tree = ast.parse(source, filename=relative)
        visitor = _SourceVisitor(file=relative, lines=source.splitlines())
        visitor.visit(tree)
        calls.extend(visitor.calls)
        definitions.extend(visitor.definitions)
        text_reads.extend(visitor.text_reads)
    text_reads = _deduplicate_text_reads(text_reads)
    return {
        "calls": calls,
        "definitions": definitions,
        "text_reads": text_reads,
        "source_hash": _stable_hash(source_parts),
        "scanned_files": [item[0] for item in source_parts],
    }


def _build_edges(index: Mapping[str, Any], firewall: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    calls = list(index["calls"])
    definitions = list(index["definitions"])
    for spec in _TRANSITIONS:
        sites = [
            site
            for site in calls
            if site.call.endswith(spec.call_suffix)
            and not _is_delegating_wrapper(site, spec.call_suffix)
        ]
        if not sites:
            continue
        if spec.call_suffix == "recognize_conversational_act" and _legacy_act_is_prefirewall(calls):
            key = (
                spec.source,
                spec.target,
                "legacy_conversational_act_adapter",
                "semantic_authority_pilot",
                "legacy_prefirewall_comparison",
                "legacy_validation",
                "immutable_candidate",
            )
            grouped[key].extend(site.to_dict() for site in sites)
            continue
        key = (
            spec.source,
            spec.target,
            spec.producer,
            spec.consumer,
            spec.dependency_type,
            spec.authority,
            spec.mutability,
        )
        grouped[key].extend(site.to_dict() for site in sites)
    for spec in _DEFINITION_TRANSITIONS:
        sites = [
            site
            for site in definitions
            if _definition_matches(site.function, spec.function)
        ]
        if not sites:
            continue
        key = (
            spec.source,
            spec.target,
            spec.producer,
            spec.consumer,
            spec.dependency_type,
            spec.authority,
            spec.mutability,
        )
        grouped[key].extend(site.to_dict() for site in sites)
    for item in firewall:
        target = str(item.get("artifact") or "")
        if target not in _NODE_BLUEPRINTS or target == "user_text":
            continue
        if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS":
            continue
        key = (
            "user_text",
            target,
            str(item["component"]),
            str(item["component"]),
            "hidden_text_dependency",
            "legacy_text_dependency",
            "read_only" if item["impact"] in {"output_only", "observability"} else "state_or_decision_input",
        )
        grouped[key].append(
            {
                "file": item["file"],
                "function": item["function"],
                "line": item["line"],
                "expression": item["expression"],
            }
        )
    edges: list[dict[str, Any]] = []
    for index_number, (key, evidence) in enumerate(sorted(grouped.items()), 1):
        source, target, producer, consumer, dependency_type, authority, mutability = key
        unique_evidence = _unique_dicts(evidence, ("file", "function", "line", "expression"))
        edges.append(
            {
                "id": f"edge-{index_number:03d}",
                "source": source,
                "target": target,
                "producer": producer,
                "consumer": consumer,
                "dependency_type": dependency_type,
                "authority": authority,
                "mutability": mutability,
                "evidence": unique_evidence,
            }
        )
    return edges


def _semantic_firewall_audit(
    text_reads: Sequence[_TextRead],
    calls: Sequence[_CallSite],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    legacy_act_prefirewall = _legacy_act_is_prefirewall(calls)
    for read in text_reads:
        if legacy_act_prefirewall and _is_legacy_conversational_act_read(read, calls):
            component = "legacy_conversational_act_adapter"
            purpose = "pre-firewall Legacy comparison and atomic rollback candidate"
            impact = "comparison_and_rollback"
            severity = "low"
            phase = "pre_semantic_compatibility"
            classification = "LEGACY_PREFIREWALL_COMPARISON_ACCESS"
        else:
            component, purpose, impact, severity, phase, violation = _classify_text_read(read)
            classification = (
                "SEMANTIC_FIREWALL_VIOLATION" if violation else "ALLOWED_TEXT_ACCESS"
            )
        output.append(
            {
                "classification": classification,
                "file": read.file,
                "function": read.function,
                "line": read.line,
                "source_kind": read.source_kind,
                "expression": read.expression,
                "source_line": read.source_line,
                "component": component,
                "purpose": purpose,
                "impact": impact,
                "severity": severity,
                "phase": phase,
                "artifact": _artifact_for_text_read(read, component),
            }
        )
    return sorted(output, key=lambda item: (item["file"], item["line"], item["expression"]))


def _legacy_act_is_prefirewall(calls: Sequence[_CallSite]) -> bool:
    begin_turn_calls = [
        call
        for call in calls
        if call.file == "aca_os/conversation_manager.py"
        and call.function == "ConversationManager.begin_turn"
    ]
    legacy_lines = [
        call.line
        for call in begin_turn_calls
        if call.call.endswith("recognize_conversational_act")
    ]
    semantic_lines = [
        call.line
        for call in begin_turn_calls
        if call.call.endswith("semantic_authority.interpret")
    ]
    return bool(legacy_lines and semantic_lines and max(legacy_lines) < min(semantic_lines))


def _is_legacy_conversational_act_read(
    read: _TextRead,
    calls: Sequence[_CallSite],
) -> bool:
    if read.file == "aca_os/conversation_manager.py":
        legacy_call_lines = [
            call.line
            for call in calls
            if call.file == read.file
            and call.function == read.function
            and call.call.endswith("recognize_conversational_act")
        ]
        return bool(
            read.function == "ConversationManager.begin_turn"
            and read.source_kind == "event.payload"
            and any(line <= read.line <= line + 3 for line in legacy_call_lines)
        )
    return (
        read.file == "aca_os/conversation_state.py"
        and read.function.split(".")[-1] == "recognize_conversational_act"
    )


def _classify_text_read(read: _TextRead) -> tuple[str, str, str, str, str, bool]:
    file = read.file
    function = read.function
    source = read.source_line
    if file == "aca_os/conversation_manager.py" and function == "ConversationSession.add_turn":
        return "conversation_manager", "pre-semantic turn capture", "transport", "none", "pre_semantic", False
    if file == "aca_os/semantic_authority.py":
        return "semantic_authority", "single authorized semantic interpretation", "semantic_authority", "none", "semantic_authority", False
    if file in {"aca_os/runtime_timeline.py", "aca_os/session.py"}:
        return Path(file).stem, "trace or session serialization", "observability", "low", "post_semantic", False
    purpose = _text_purpose(source, function)
    if file == "aca_os/runtime.py":
        return "runtime", purpose or "intent matching or plan reconstruction", "routing_and_planning", "critical", "post_semantic", True
    if file == "aca_os/conversation_manager.py":
        severity = "critical" if any(
            marker in source
            for marker in (
                "model_conversational_intent",
                "plan_information_gain",
                "plan_conversation",
                "plan_conversational_response",
            )
        ) else "high"
        return "conversation_manager", purpose or "legacy conversational derivation", "conversation_state_decision", severity, "post_semantic", True
    if "recognize_conversational_act" in source:
        return "conversation_state", "legacy conversational-act recognition", "conversation_state_decision", "high", "post_semantic", True
    if "resolve_pending_slot_answers" in source:
        return "conversation_state", "legacy pending-slot resolution", "conversation_state_decision", "high", "post_semantic", True
    if "assimilate_user_facts" in source:
        return "conversation_state", "legacy fact assimilation", "conversation_state_decision", "high", "post_semantic", True
    if "update_topic_stack" in source:
        return "conversation_state", "legacy topic transition", "conversation_state_decision", "high", "post_semantic", True
    if "apply_conversational_goal" in source:
        return "conversation_state", "legacy conversational-goal selection", "conversation_state_decision", "high", "post_semantic", True
    if "model_conversational_intent" in source or function.endswith("model_conversational_intent"):
        return "conversation_state", "legacy intent-model construction", "planning_input", "critical", "post_semantic", True
    if "plan_information_gain" in source or function.endswith("plan_information_gain"):
        return "conversation_state", "legacy clarification planning", "planning_input", "critical", "post_semantic", True
    if "plan_conversational_response" in source or function.endswith("plan_conversational_response"):
        return "conversation_state", "legacy response-plan construction", "planning_input", "critical", "post_semantic", True
    if "plan_conversation" in source or function.endswith("plan_conversation"):
        return "conversation_state", "legacy conversation planning", "planning_input", "critical", "post_semantic", True
    if file == "aca_os/mission_manager.py":
        return "mission_manager", "mission selection from free text", "mission_selection", "critical", "post_semantic", True
    if file == "aca_os/policy_manager.py":
        return "policy_manager", "policy evaluation from free text", "safety_decision", "critical", "post_semantic", True
    if file == "zero_cost/intent_matcher.py":
        return "intent_matcher", "lexical intent classification", "routing_and_planning", "critical", "post_semantic", True
    if file.startswith("kernel/"):
        return "kernel", "kernel program selection or entity extraction", "cognitive_execution", "high", "post_semantic", True
    if file == "aca_os/narrative_response_composer.py":
        return "narrative_response_composer", "surface realization from current user text", "output_only", "medium", "post_semantic", True
    if file == "aca_os/llm_verbalization.py":
        return "llm_verbalizer", "verbalization grounding or validation", "output_only", "low", "post_semantic", True
    if file == "aca_os/operational_work_mapper.py":
        return "operational_work_mapper", "shadow work inference from raw text", "shadow_only", "medium", "post_semantic", True
    if file.startswith("plugins/"):
        return "plugin_semantic", "plugin-local semantic parsing", "alternate_semantic_authority", "high", "post_semantic", True
    return Path(file).stem, "free-text dependent derivation", "state_or_decision", "high", "post_semantic", True


def _text_purpose(source: str, function: str) -> str:
    markers = (
        ("recognize_conversational_act", "legacy conversational-act recognition"),
        ("resolve_pending_slot_answers", "legacy pending-slot resolution"),
        ("assimilate_user_facts", "legacy fact assimilation"),
        ("update_topic_stack", "legacy topic transition"),
        ("apply_conversational_goal", "legacy conversational-goal selection"),
        ("model_conversational_intent", "legacy intent-model construction"),
        ("plan_information_gain", "legacy clarification planning"),
        ("plan_conversational_response", "legacy response-plan construction"),
        ("plan_conversation", "legacy conversation planning"),
        ("intent_matcher.match", "lexical intent classification"),
    )
    for marker, purpose in markers:
        if marker in source or marker == function.split(".")[-1]:
            return purpose
    return ""


def _artifact_for_text_read(read: _TextRead, component: str) -> str:
    source = read.source_line
    function = read.function.split(".")[-1]
    markers = (
        ("recognize_conversational_act", "conversational_act"),
        ("resolve_pending_slot_answers", "slot_state"),
        ("assimilate_user_facts", "conversation_facts"),
        ("update_topic_stack", "topic_state"),
        ("apply_conversational_goal", "conversational_goal"),
        ("model_conversational_intent", "conversation_intent_model"),
        ("plan_information_gain", "information_gain_plan"),
        ("plan_conversational_response", "conversation_response_plan"),
        ("plan_conversation", "conversation_plan"),
        ("intent_matcher.match", "intent_match"),
    )
    for marker, artifact in markers:
        if marker in source or marker == function:
            return artifact
    if component == "legacy_conversational_act_adapter":
        return "conversational_act"
    if component == "mission_manager":
        return "mission"
    if component == "policy_manager":
        return "policy_result"
    if component == "intent_matcher":
        return "intent_match"
    if component == "kernel":
        if "Extract" in read.function:
            return "kernel_entities"
        if "Observe" in read.function:
            return "conversation_facts"
        return "kernel_program"
    if component == "narrative_response_composer":
        return "narrative_response"
    if component == "llm_verbalizer":
        return "verbalized_response"
    if component == "operational_work_mapper":
        return "candidate_work"
    if component == "plugin_semantic":
        return "kernel_entities"
    return "user_text"


def _recomputation_audit(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for edge in edges:
        evidence = list(edge.get("evidence") or [])
        if edge["dependency_type"] == "legacy_recomputation" and len(evidence) > 1:
            output.append(
                {
                    "artifact": edge["target"],
                    "type": "RECOMPUTED_AND_OVERWRITTEN",
                    "producer": edge["producer"],
                    "occurrence_count": len(evidence),
                    "first_write": dict(evidence[0]),
                    "overwriting_writes": [dict(item) for item in evidence[1:]],
                    "authority": edge["authority"],
                    "impact": "The later Legacy calculation replaces the earlier turn projection.",
                }
            )
    incoming: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for edge in edges:
        incoming[str(edge["target"])].append(edge)
    for artifact in ("conversational_act", "conversational_goal", "intent_match", "cognitive_state", "runtime_outcomes"):
        producers = sorted({str(item["producer"]) for item in incoming.get(artifact, [])})
        if len(producers) < 2:
            continue
        output.append(
            {
                "artifact": artifact,
                "type": (
                    "GUARDED_MULTI_AUTHORITY"
                    if artifact in _GUARDED_MULTI_AUTHORITY_ARTIFACTS
                    else "MULTIPLE_WRITERS"
                ),
                "producer": producers,
                "occurrence_count": sum(len(item.get("evidence") or []) for item in incoming[artifact]),
                "first_write": dict((incoming[artifact][0].get("evidence") or [{}])[0]),
                "overwriting_writes": [
                    dict(evidence)
                    for item in incoming[artifact][1:]
                    for evidence in item.get("evidence") or []
                ],
                "authority": sorted({str(item["authority"]) for item in incoming[artifact]}),
                "impact": (
                    "SA-3/SA-5 selects one complete authority atomically."
                    if artifact in _GUARDED_MULTI_AUTHORITY_ARTIFACTS
                    else "Multiple components can replace or transform the same artifact."
                ),
            }
        )
    return sorted(output, key=lambda item: (item["artifact"], item["type"]))


def _build_nodes(
    edges: Sequence[Mapping[str, Any]],
    firewall: Sequence[Mapping[str, Any]],
    recomputations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    incoming: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for edge in edges:
        incoming[str(edge["target"])].append(edge)
        outgoing[str(edge["source"])].append(edge)
    text_dependent = {
        str(item["artifact"])
        for item in firewall
        if item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
    }
    recomputed = {str(item["artifact"]) for item in recomputations}
    nodes: list[dict[str, Any]] = []
    for artifact_id, blueprint in _NODE_BLUEPRINTS.items():
        classifications = set(blueprint["classifications"])
        if artifact_id in text_dependent:
            classifications.add("TEXT_DEPENDENT")
        if artifact_id in recomputed:
            classifications.add("RECOMPUTED")
        authority_score = _authority_score(incoming.get(artifact_id, []))
        evidence = [
            dict(item)
            for edge in incoming.get(artifact_id, [])
            for item in edge.get("evidence") or []
        ]
        nodes.append(
            {
                "id": artifact_id,
                "label": blueprint["label"],
                "owner": blueprint["owner"],
                "classifications": sorted(classifications),
                "effective_authority": _effective_authority(artifact_id, incoming.get(artifact_id, [])),
                "mutable": blueprint["mutable"],
                "side_effects": blueprint["side_effects"],
                "promotion_candidate": blueprint["promotion_candidate"],
                "never_promote_reason": blueprint["never_promote_reason"],
                "authority_score": authority_score,
                "producer_count": len({edge["producer"] for edge in incoming.get(artifact_id, [])}),
                "consumer_count": len({edge["consumer"] for edge in outgoing.get(artifact_id, [])}),
                "coupling": len(incoming.get(artifact_id, [])) + len(outgoing.get(artifact_id, [])),
                "rollback": _rollback_profile(artifact_id, blueprint, incoming, outgoing),
                "source_locations": _unique_dicts(evidence, ("file", "function", "line")),
            }
        )
    return nodes


def _promotion_readiness(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    firewall: Sequence[Mapping[str, Any]],
    recomputations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    violations = Counter(
        str(item["artifact"])
        for item in firewall
        if item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
    )
    critical_violations = Counter(
        str(item["artifact"])
        for item in firewall
        if item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
        and item["severity"] == "critical"
    )
    recomputed = {str(item["artifact"]) for item in recomputations}
    output: list[dict[str, Any]] = []
    for node in nodes:
        artifact = str(node["id"])
        reasons: list[str] = []
        if artifact == "conversational_act":
            status = "READY"
            reasons.append("Already promoted only for gated high-confidence greetings with atomic Legacy rollback.")
        elif artifact == "conversational_goal":
            status = "READY"
            reasons.append("Already promoted only when projection validity, confidence, decision agreement and state-effect parity all pass, with atomic Legacy rollback.")
        elif node.get("never_promote_reason"):
            status = "BLOCKED"
            reasons.append(str(node["never_promote_reason"]))
        elif artifact in recomputed:
            status = "BLOCKED"
            reasons.append("A later writer recomputes or overwrites this artifact in the official pipeline.")
        elif node.get("side_effects"):
            status = "HIGH_RISK"
            reasons.append("The artifact participates in safety or external side effects.")
        elif critical_violations[artifact]:
            status = "HIGH_RISK"
            reasons.append("Critical post-semantic free-text dependencies still govern this artifact.")
        elif violations[artifact] and node.get("mutable"):
            status = "HIGH_RISK"
            reasons.append("The artifact is mutable and still derived from raw text after SemanticAuthority.")
        elif violations[artifact]:
            status = "MEDIUM_RISK"
            reasons.append("The artifact still has a post-semantic free-text dependency.")
        elif int(node.get("coupling") or 0) >= 5:
            status = "MEDIUM_RISK"
            reasons.append("The artifact has high producer/consumer coupling.")
        elif node.get("promotion_candidate"):
            status = "LOW_RISK"
            reasons.append("No overwrite or critical text dependency was detected.")
        else:
            status = "BLOCKED"
            reasons.append("This is not a direct semantic promotion target.")
        output.append(
            {
                "artifact": artifact,
                "status": status,
                "reason": " ".join(reasons),
                "text_dependency_count": violations[artifact],
                "critical_text_dependency_count": critical_violations[artifact],
                "recomputed": artifact in recomputed,
                "coupling": node.get("coupling", 0),
                "rollback": dict(node.get("rollback") or {}),
                "promotion_candidate": bool(node.get("promotion_candidate")),
            }
        )
    return sorted(output, key=lambda item: item["artifact"])


def _promotion_order(readiness: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rank = {"READY": 0, "LOW_RISK": 1, "MEDIUM_RISK": 2, "HIGH_RISK": 3, "BLOCKED": 4}
    candidates = [item for item in readiness if item.get("promotion_candidate")]
    ordered = sorted(
        candidates,
        key=lambda item: (
            rank[str(item["status"])],
            int(item.get("coupling") or 0),
            int(item.get("text_dependency_count") or 0),
            str(item["artifact"]),
        ),
    )
    return [
        {
            "position": position,
            "artifact": item["artifact"],
            "readiness": item["status"],
            "reason": item["reason"],
            "rollback": item["rollback"],
        }
        for position, item in enumerate(ordered, 1)
    ]


def _find_dependency_cycles(
    nodes: Mapping[str, Any],
    edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    evidence_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        if source == target:
            continue
        adjacency.setdefault(source, set()).add(target)
        evidence_by_pair[(source, target)].append(str(edge["producer"]))

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(adjacency.get(node, set())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] != indices[node]:
            return
        component: list[str] = []
        while stack:
            current = stack.pop()
            on_stack.remove(current)
            component.append(current)
            if current == node:
                break
        if len(component) > 1:
            components.append(sorted(component))

    for node in sorted(adjacency):
        if node not in indices:
            visit(node)

    output: list[dict[str, Any]] = []
    for number, component in enumerate(sorted(components), 1):
        internal_edges = [
            {
                "source": source,
                "target": target,
                "producers": sorted(set(producers)),
            }
            for (source, target), producers in evidence_by_pair.items()
            if source in component and target in component
        ]
        output.append(
            {
                "id": f"cycle-{number:02d}",
                "nodes": component,
                "edges": sorted(internal_edges, key=lambda item: (item["source"], item["target"])),
                "impact": "Authority can return to an earlier state representation after downstream processing.",
            }
        )
    return output


def _runtime_observation(runtime_trace: Mapping[str, Any] | None) -> dict[str, Any]:
    if not runtime_trace:
        return {
            "trace_available": False,
            "observed_operations": [],
            "observed_artifacts": [],
            "authority_events": [],
        }
    operations = list(runtime_trace.get("operations") or [])
    if not operations:
        operations = [
            str(item.get("operation") or "")
            for item in runtime_trace.get("events") or []
            if isinstance(item, Mapping)
        ]
    observed = sorted(
        {
            artifact
            for operation in operations
            if (artifact := _TRACE_OPERATION_ARTIFACTS.get(str(operation)))
        }
    )
    authority_events = [
        dict(item)
        for item in runtime_trace.get("events") or []
        if isinstance(item, Mapping)
        and str(item.get("operation") or "").startswith("SEMANTIC_")
    ]
    return {
        "trace_available": True,
        "trace_id": runtime_trace.get("trace_id"),
        "observed_operations": operations,
        "observed_artifacts": observed,
        "authority_events": authority_events,
    }


def _build_report(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    firewall: Sequence[Mapping[str, Any]],
    recomputations: Sequence[Mapping[str, Any]],
    cycles: Sequence[Mapping[str, Any]],
    readiness: Sequence[Mapping[str, Any]],
    promotion_order: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    readiness_counts = Counter(str(item["status"]) for item in readiness)
    violations = [
        item for item in firewall if item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
    ]
    blocked = [item for item in readiness if item["status"] == "BLOCKED"]
    never_promote = [
        {
            "artifact": node["id"],
            "reason": node["never_promote_reason"],
        }
        for node in nodes
        if node.get("never_promote_reason")
    ]
    return {
        "contract": "authority_dependency_report.v1",
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "semantic_firewall_violation_count": len(violations),
            "critical_firewall_violation_count": sum(item["severity"] == "critical" for item in violations),
            "recomputation_count": len(recomputations),
            "dependency_cycle_count": len(cycles),
            "readiness_distribution": dict(sorted(readiness_counts.items())),
        },
        "ready_for_promotion": [
            item["artifact"] for item in readiness if item["status"] in {"READY", "LOW_RISK"}
        ],
        "blocked_components": [
            {"artifact": item["artifact"], "reason": item["reason"]}
            for item in blocked
        ],
        "next_promotion_candidate": next(
            (
                item
                for item in promotion_order
                if item["artifact"] != "conversational_act"
            ),
            {},
        ),
        "never_promote_directly": never_promote,
        "critical_dependencies": [
            {
                "artifact": item["artifact"],
                "component": item["component"],
                "file": item["file"],
                "function": item["function"],
                "line": item["line"],
            }
            for item in violations
            if item["severity"] == "critical"
        ],
        "redundant_consumers": [
            {
                "artifact": item["artifact"],
                "type": item["type"],
                "occurrence_count": item["occurrence_count"],
            }
            for item in recomputations
        ],
        "simplification_opportunities": [
            "Remove post-Mission Legacy recomputation only when each affected artifact has a promoted structured source and per-turn rollback.",
            "Replace direct event.payload consumers with explicit projections one vertical at a time.",
            "Keep Policy, Governance, execution outcomes, tools, output realization, and Ledger outside semantic authority.",
        ],
    }


def _authority_score(incoming: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    if not incoming:
        return {
            "own_authority": 1.0,
            "inherited_authority": 0.0,
            "shared_authority": 0.0,
            "overwritten_authority": 0.0,
        }
    counts = Counter()
    for edge in incoming:
        authority = str(edge.get("authority") or "")
        if authority in {"legacy_primary", "semantic_primary", "independent_primary", "execution_primary"}:
            counts["own_authority"] += 1
        elif authority in {"semantic_conditional", "shared", "legacy_or_validation"}:
            counts["shared_authority"] += 1
        elif authority in {"legacy_recomputed", "overwritten"}:
            counts["overwritten_authority"] += 1
        else:
            counts["inherited_authority"] += 1
    total = sum(counts.values()) or 1
    return {
        name: round(counts[name] / total, 4)
        for name in (
            "own_authority",
            "inherited_authority",
            "shared_authority",
            "overwritten_authority",
        )
    }


def _effective_authority(artifact_id: str, incoming: Sequence[Mapping[str, Any]]) -> str:
    if artifact_id == "conversation_state":
        return "primary_state_owner"
    if artifact_id == "cognitive_state":
        return "runtime_state_owner"
    if artifact_id == "conversational_act":
        return "semantic_pilot_for_greeting_else_legacy"
    if artifact_id == "conversational_goal":
        return "semantic_pilot_with_parity_gate_else_legacy"
    if artifact_id in {"semantic_representation", "semantic_projection", "candidate_work", "case_state_projection", "governance_assessment", "operational_ledger"}:
        return "shadow"
    if artifact_id in {"policy_result", "tool_execution", "runtime_outcomes"}:
        return "independent_operational_authority"
    if any(edge.get("authority") == "legacy_recomputed" for edge in incoming):
        return "legacy_recomputed"
    if any(str(edge.get("authority") or "").startswith("legacy") for edge in incoming):
        return "legacy"
    if incoming:
        return "derived"
    return "source"


def _rollback_profile(
    artifact_id: str,
    blueprint: Mapping[str, Any],
    incoming: Mapping[str, Sequence[Mapping[str, Any]]],
    outgoing: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    coupling = len(incoming.get(artifact_id, [])) + len(outgoing.get(artifact_id, []))
    if artifact_id == "conversational_act":
        level = "easy"
        impact = "Turn-scoped atomic selector already falls back to complete Legacy value."
    elif blueprint.get("side_effects"):
        level = "hard"
        impact = "Rollback may require safety review, idempotency, or compensation."
    elif blueprint.get("mutable") and "STATE_DEPENDENT" in blueprint.get("classifications", []):
        level = "moderate"
        impact = "Rollback must restore or reproject state without mixing authorities."
    elif coupling >= 5:
        level = "moderate"
        impact = "Several downstream consumers must observe the same authority switch."
    else:
        level = "easy"
        impact = "Immutable or output-only projection can be replaced as one value."
    return {
        "level": level,
        "impact": impact,
        "side_effects": bool(blueprint.get("side_effects")),
        "coupling": coupling,
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _definition_matches(actual: str, expected: str) -> bool:
    if "." in expected:
        return actual.endswith(expected)
    return actual.split(".")[-1] == expected


def _is_delegating_wrapper(site: _CallSite, call_suffix: str) -> bool:
    """Ignore ConversationState methods that only delegate to same-named helpers."""
    return (
        site.file == "aca_os/conversation_state.py"
        and site.function.split(".")[-1] == call_suffix.split(".")[-1]
    )


def _root_name(node: ast.AST) -> str:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _deduplicate_text_reads(values: Iterable[_TextRead]) -> list[_TextRead]:
    output: list[_TextRead] = []
    seen: set[tuple[Any, ...]] = set()
    for item in values:
        key = (item.file, item.function, item.line)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _is_authoritative_free_text_parameter(file: str, function: str) -> bool:
    tail = function.split(".")[-1]
    if file == "zero_cost/intent_matcher.py" and tail == "match":
        return True
    if file.startswith("plugins/") and tail == "analyze":
        return True
    if file == "aca_os/conversation_state.py" and tail in {
        "resolve_pending_slot_answers",
        "model_conversational_intent",
        "plan_information_gain",
        "plan_conversation",
        "plan_conversational_response",
        "update_topic_stack",
        "recognize_conversational_act",
        "_new_unresolved_topic",
        "assimilate_user_facts",
    }:
        return True
    return False


def _unique_dicts(values: Iterable[Mapping[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in values:
        key = tuple(item.get(name) for name in keys)
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(item))
    return sorted(output, key=lambda item: tuple(str(item.get(name) or "") for name in keys))


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _mermaid_id(value: str) -> str:
    return "N_" + "".join(character if character.isalnum() else "_" for character in value)
