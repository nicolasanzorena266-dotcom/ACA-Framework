from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from aca_os.authority_dependency_graph import build_authority_dependency_graph


SEMANTIC_FIREWALL_PLAN_CONTRACT = "semantic_firewall_refactoring_plan.v1"
SEMANTIC_FIREWALL_PLAN_VERSION = "fw-1"


@dataclass(frozen=True)
class SemanticFirewallRefactoringPlan:
    repository_root: Path
    authority_source_hash: str
    authority_graph_hash: str
    inventory: tuple[dict[str, Any], ...]
    replacement_matrix: tuple[dict[str, Any], ...]
    migration_packages: tuple[dict[str, Any], ...]
    elimination_order: tuple[dict[str, Any], ...]
    recomputation_report: dict[str, Any]
    dependency_collapse_candidates: tuple[dict[str, Any], ...]
    promotion_forecast: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    plan_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": SEMANTIC_FIREWALL_PLAN_CONTRACT,
            "version": SEMANTIC_FIREWALL_PLAN_VERSION,
            "repository_root": str(self.repository_root),
            "authority_source_hash": self.authority_source_hash,
            "authority_graph_hash": self.authority_graph_hash,
            "plan_hash": self.plan_hash,
            "summary": dict(self.summary),
            "inventory": [dict(item) for item in self.inventory],
            "replacement_matrix": [dict(item) for item in self.replacement_matrix],
            "migration_packages": [dict(item) for item in self.migration_packages],
            "elimination_order": [dict(item) for item in self.elimination_order],
            "recomputation_report": dict(self.recomputation_report),
            "dependency_collapse_candidates": [
                dict(item) for item in self.dependency_collapse_candidates
            ],
            "promotion_forecast": [dict(item) for item in self.promotion_forecast],
        }

    def inspect_consumer(self, consumer_id: str) -> dict[str, Any]:
        item = next(
            (entry for entry in self.inventory if entry["consumer_id"] == consumer_id),
            None,
        )
        if item is None:
            raise KeyError(f"Unknown semantic firewall consumer: {consumer_id}")
        return dict(item)

    def inventory_mermaid(self) -> str:
        lines = [
            "flowchart LR",
            '    TXT["Original user text"]',
            '    FW["Semantic firewall"]',
            '    SEM["SemanticRepresentation and projections"]',
            '    TXT --> FW --> SEM',
        ]
        package_by_id = {item["package_id"]: item for item in self.migration_packages}
        for package in self.elimination_order:
            package_id = str(package["package_id"])
            definition = package_by_id[package_id]
            node_id = _mermaid_id(package_id)
            label = str(definition["name"]).replace('"', "'")
            lines.append(f'    {node_id}["{package_id}: {label}"]')
            if definition["disposition"] == "KEEP_ALLOWED":
                lines.append(f"    TXT -.-> {node_id}")
            elif definition["disposition"] == "KEEP_CONSTRAINED":
                lines.append(f"    SEM --> {node_id}")
                lines.append(f"    TXT -. \"output-only envelope\" .-> {node_id}")
            else:
                lines.append(f"    SEM --> {node_id}")
        return "\n".join(lines)

    def recomputation_mermaid(self) -> str:
        return str(self.recomputation_report["mermaid"])


_REPLACEMENTS: dict[str, dict[str, str]] = {
    "conversational_act": {
        "information_used": "Conversational function of the current turn and its confidence.",
        "replacement_source": "SemanticProjection",
        "replacement_field": "conversational_act",
        "replacement_status": "READY_WITH_EXISTING_TURN_ROLLBACK",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Structured act value only; Legacy remains atomic rollback during migration.",
        "package_id": "FW-4",
        "promotion_impact": "ConversationalAct can retire its Legacy text recognizer after pilot thresholds hold.",
    },
    "slot_state": {
        "information_used": "Answers, values, negation, confidence, and evidence for pending slots.",
        "replacement_source": "SemanticProjection and SemanticRepresentation",
        "replacement_field": "slot_projection + proposed_state_delta + assertions + provenance",
        "replacement_status": "PROJECTED_NOT_AUTHORITATIVE",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Slot lifecycle consumes a typed answer projection and never the utterance.",
        "package_id": "FW-7",
        "promotion_impact": "SlotState becomes eligible for a turn-scoped semantic pilot.",
    },
    "conversation_facts": {
        "information_used": "Assertions, negation, correction, retraction, evidence, and temporal scope.",
        "replacement_source": "SemanticProjection and SemanticRepresentation",
        "replacement_field": "fact_projection + assertions + corrections + contradictions + provenance",
        "replacement_status": "PROJECTED_NOT_AUTHORITATIVE",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Fact assimilation receives typed assertions; raw payload is not stored as a fact.",
        "package_id": "FW-8",
        "promotion_impact": "ConversationFacts becomes eligible after slot/fact state rollback is atomic.",
    },
    "topic_state": {
        "information_used": "Topic boundaries, active topic, transitions, references, and priority.",
        "replacement_source": "SemanticProjection and SemanticRepresentation",
        "replacement_field": "topic_projection + topic_structure + semantic_segments",
        "replacement_status": "PROJECTED_NOT_AUTHORITATIVE",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Topic lifecycle consumes topic identities and transitions, not normalized text.",
        "package_id": "FW-6",
        "promotion_impact": "TopicState becomes eligible for a turn-scoped semantic pilot.",
    },
    "conversational_goal": {
        "information_used": "Explicit and implicit goals, priority, and relation to the active topic.",
        "replacement_source": "SemanticProjection and SemanticRepresentation",
        "replacement_field": "goal_projection + goals + topic_structure",
        "replacement_status": "NEXT_HIGH_RISK_VERTICAL",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Goal lifecycle consumes a complete semantic goal projection.",
        "package_id": "FW-5",
        "promotion_impact": "ConversationalGoal becomes the next low-coupling promotion candidate.",
    },
    "conversation_intent_model": {
        "information_used": "Explicit questions, implicit needs, concern, goals, assumptions, and uncertainty.",
        "replacement_source": "SemanticProjection",
        "replacement_field": "conversation_intent_model",
        "replacement_status": "BLOCKED_BY_DUPLICATE_WRITER",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "ConversationIntentModel receives one complete projection per turn.",
        "package_id": "FW-10",
        "promotion_impact": "Removes direct-text construction but remains blocked until FW-11 collapses the second writer.",
    },
    "information_gain_plan": {
        "information_used": "Missing information, uncertainty, affected decisions, and pending questions.",
        "replacement_source": "Authoritative ConversationIntentModel plus SemanticRepresentation",
        "replacement_field": "uncertainty + goals + constraints + grounding",
        "replacement_status": "DERIVE_AFTER_FIREWALL",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "Planner remains authoritative for question value and consumes structured inputs only.",
        "package_id": "FW-11",
        "promotion_impact": "InformationGainPlan remains derived; its duplicate Runtime write can disappear.",
    },
    "conversation_plan": {
        "information_used": "Goal, selected clarification, completed work, pending steps, and topic continuity.",
        "replacement_source": "ConversationIntentModel, InformationGainPlan, and ConversationState",
        "replacement_field": "authoritative structured planning inputs",
        "replacement_status": "DERIVE_AFTER_FIREWALL",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "ConversationPlan remains a planner output and never receives free text.",
        "package_id": "FW-11",
        "promotion_impact": "ConversationPlan remains derived; its duplicate Runtime write can disappear.",
    },
    "conversation_response_plan": {
        "information_used": "Primary need, response priority, next action, and justified questions.",
        "replacement_source": "ConversationPlan and ConversationIntentModel",
        "replacement_field": "authoritative structured response inputs",
        "replacement_status": "DERIVE_AFTER_FIREWALL",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "Response planning consumes the plan and intent model, not the utterance.",
        "package_id": "FW-11",
        "promotion_impact": "ConversationResponsePlan remains derived; its duplicate Runtime write can disappear.",
    },
    "intent_match": {
        "information_used": "Domain intent, confidence, evidence, and ambiguity.",
        "replacement_source": "SemanticProjection",
        "replacement_field": "intent_projection + intents + grounding + uncertainty",
        "replacement_status": "BLOCKED_BY_ROUTING_COUPLING",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "IntentMatcher becomes a compatibility adapter over one complete projection.",
        "package_id": "FW-12",
        "promotion_impact": "IntentMatch becomes eligible only after CIM and state projections are stable.",
    },
    "mission": {
        "information_used": "Operational goal, event, domain intent, case facts, and current mission state.",
        "replacement_source": "SemanticRepresentation, IntentMatch, ExecutionPlan, and ConversationState",
        "replacement_field": "goals + events + intents + assertions + active mission",
        "replacement_status": "STRUCTURED_CONSUMER_ONLY",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "MissionManager keeps mission authority but cannot reclassify the utterance.",
        "package_id": "FW-14",
        "promotion_impact": "MissionManager is firewall-compliant; it is never promoted to semantic authority.",
    },
    "policy_result": {
        "information_used": "Safety constraints, risk signals, uncertainty, requested operation, and evidence.",
        "replacement_source": "SemanticRepresentation, ExecutionPlan, Policy, and ConversationState",
        "replacement_field": "constraints + grounding + uncertainty + selected operation",
        "replacement_status": "INDEPENDENT_AUTHORITY_REQUIRES_PARITY",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "Policy keeps independent veto authority and receives a constrained safety projection.",
        "package_id": "FW-15",
        "promotion_impact": "Policy becomes firewall-compliant but never cedes authority to semantics.",
    },
    "kernel_program": {
        "information_used": "Program selection implied by intent, action, flow, and execution plan.",
        "replacement_source": "ExecutionPlan",
        "replacement_field": "steps + selected flow + action",
        "replacement_status": "DERIVE_FROM_EXECUTION_PLAN",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "GraphCompiler compiles an ExecutionPlan and stops interpreting user text.",
        "package_id": "FW-13",
        "promotion_impact": "Kernel program selection remains derived and loses its parallel classifier.",
    },
    "kernel_entities": {
        "information_used": "Entities, relations, types, confidence, and source evidence.",
        "replacement_source": "SemanticProjection and SemanticRepresentation",
        "replacement_field": "entity_projection + entities + relations + provenance",
        "replacement_status": "PROJECTED_NOT_AUTHORITATIVE",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Kernel and plugins consume one entity projection; plugin rules enrich vocabulary upstream.",
        "package_id": "FW-9",
        "promotion_impact": "KernelEntities becomes eligible and duplicate plugin parsers can retire.",
    },
    "candidate_work": {
        "information_used": "User need, operational facts, active topic, mission, and selected plan.",
        "replacement_source": "SemanticProjection, ConversationState, and ExecutionPlan",
        "replacement_field": "goals + fact_projection + topic_projection + structured plans",
        "replacement_status": "SHADOW_SAFE_TO_REPLACE",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
        "target_access": "Shadow mapper consumes existing projections and removes last_raw_payload fallback.",
        "package_id": "FW-3",
        "promotion_impact": "No cognitive promotion; Candidate Work remains Shadow and becomes firewall-clean.",
    },
    "narrative_response": {
        "information_used": "Exact current wording for acknowledgement and natural continuity.",
        "replacement_source": "Output-only utterance envelope",
        "replacement_field": "recent_user_utterance.display_text",
        "replacement_status": "KEEP_ONLY_BEHIND_OUTPUT_BOUNDARY",
        "disposition": "KEEP_CONSTRAINED",
        "target_access": "Composer may quote or acknowledge text but cannot derive facts, intent, policy, or plans.",
        "package_id": "FW-2",
        "promotion_impact": "No promotion; output realization receives an enforceable non-cognitive boundary.",
    },
    "verbalized_response": {
        "information_used": "Exact current wording for natural realization and semantic fidelity checks.",
        "replacement_source": "Output-only utterance envelope",
        "replacement_field": "recent_user_utterance.display_text",
        "replacement_status": "KEEP_ONLY_BEHIND_OUTPUT_BOUNDARY",
        "disposition": "KEEP_CONSTRAINED",
        "target_access": "Verbalizer can realize existing decisions but cannot create structured meaning.",
        "package_id": "FW-2",
        "promotion_impact": "No promotion; LLM remains an output-only transform.",
    },
    "user_text": {
        "information_used": "Unresolved topic identity or label derived from the utterance.",
        "replacement_source": "SemanticProjection and SemanticRepresentation",
        "replacement_field": "topic_projection + topic_structure + semantic_segments",
        "replacement_status": "PROJECTED_NOT_AUTHORITATIVE",
        "disposition": "REPLACE_WITH_SEMANTIC",
        "target_access": "Unresolved-topic creation consumes a semantic topic segment.",
        "package_id": "FW-6",
        "promotion_impact": "TopicState becomes complete enough for a controlled pilot.",
    },
}


_PACKAGE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "FW-A0": {
        "name": "Authorized raw-text boundary allowlist",
        "goal": "Freeze the only legal raw-text reads: capture, the single SemanticAuthority interpretation, and audit serialization.",
        "dependencies": [],
        "risk": "LOW",
        "difficulty": "LOW",
        "rollback": "Remove enforcement only; no runtime value changes.",
        "acceptance": "Every allowed access has a declared non-cognitive purpose and all other reads are violations.",
        "disposition": "KEEP_ALLOWED",
    },
    "FW-2": {
        "name": "Output-only utterance boundary",
        "goal": "Constrain Composer and LLM access to presentation without semantic or operational decisions.",
        "dependencies": ["FW-A0"],
        "risk": "LOW",
        "difficulty": "LOW",
        "rollback": "Restore the current output envelope; cognitive state is untouched.",
        "acceptance": "Output text remains equivalent and no output component writes cognitive artifacts.",
        "disposition": "KEEP_CONSTRAINED",
    },
    "FW-3": {
        "name": "Shadow Candidate Work fallback removal",
        "goal": "Remove last_raw_payload fallback from Candidate Work without changing visible behavior.",
        "scope_components": ["operational_work_mapper"],
        "dependencies": ["FW-A0"],
        "risk": "LOW",
        "difficulty": "LOW",
        "rollback": "Re-enable the Shadow fallback; no official decision is affected.",
        "acceptance": "Operational benchmarks are unchanged and Candidate Work reads structured inputs only.",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
    },
    "FW-4": {
        "name": "ConversationalAct Legacy retirement",
        "goal": "Remove post-firewall act recognition after the existing semantic pilot proves full parity.",
        "dependencies": ["FW-A0"],
        "risk": "MEDIUM",
        "difficulty": "LOW",
        "rollback": "Turn-scoped atomic switch to the complete Legacy act.",
        "acceptance": "Official and adversarial act metrics meet promotion thresholds with zero mixed-authority turns.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-5": {
        "name": "ConversationalGoal semantic input",
        "goal": "Replace low-coupling goal text matching with the goal projection.",
        "dependencies": ["FW-4"],
        "risk": "MEDIUM",
        "difficulty": "MEDIUM",
        "rollback": "Select one complete Legacy goal for the turn and discard the semantic mutation.",
        "acceptance": "Goal parity, state delta parity, and rollback tests pass without response regression.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-6": {
        "name": "Topic lifecycle semantic input",
        "goal": "Drive topic creation and transitions from topic projections, including unresolved topics.",
        "dependencies": ["FW-5"],
        "risk": "MEDIUM",
        "difficulty": "MEDIUM",
        "rollback": "Restore the complete pre-turn topic stack.",
        "acceptance": "Topic transition and long-conversation benchmarks preserve active/suspended topics.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-7": {
        "name": "Pending slot semantic resolution",
        "goal": "Resolve pending slots from typed assertions and conversational act projections.",
        "dependencies": ["FW-4"],
        "risk": "MEDIUM",
        "difficulty": "MEDIUM",
        "rollback": "Restore the complete pre-turn slot and pending-question set.",
        "acceptance": "Slot lifecycle, ambiguity, out-of-order, and repeated-question benchmarks preserve parity.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-8": {
        "name": "Fact assimilation and raw-payload fact removal",
        "goal": "Assimilate typed assertions and stop persisting last_raw_payload as a cognitive fact.",
        "dependencies": ["FW-6", "FW-7"],
        "risk": "HIGH",
        "difficulty": "MEDIUM",
        "rollback": "Restore the complete fact history and mission snapshot atomically.",
        "acceptance": "Fact, negation, correction, retraction, mission-advance, and provenance parity hold.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-9": {
        "name": "Entity extraction consolidation",
        "goal": "Replace Kernel and plugin-local entity parsers with the shared entity projection.",
        "dependencies": ["FW-8"],
        "risk": "HIGH",
        "difficulty": "MEDIUM",
        "rollback": "Select complete Legacy entities for the turn; never merge entity sets.",
        "acceptance": "Entity/provenance benchmarks pass per plugin and duplicate parsers are unused.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-10": {
        "name": "ConversationIntentModel semantic construction",
        "goal": "Build one complete ConversationIntentModel from SemanticProjection without free text.",
        "dependencies": ["FW-5", "FW-6", "FW-7", "FW-8", "FW-9"],
        "risk": "HIGH",
        "difficulty": "HIGH",
        "rollback": "Select the complete Legacy model before any downstream planner runs.",
        "acceptance": "Field parity, confidence thresholds, and atomic rollback pass; no downstream text is read for CIM.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-11": {
        "name": "Structured planning and duplicate writer collapse",
        "goal": "Make planning consume structured inputs once and remove Runtime's second CIM/plan write.",
        "dependencies": ["FW-10"],
        "risk": "HIGH",
        "difficulty": "HIGH",
        "rollback": "Restore the complete Legacy planning chain for the turn before execution.",
        "acceptance": "Exactly one writer exists for CIM, InformationGainPlan, ConversationPlan, and ResponsePlan.",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
    },
    "FW-12": {
        "name": "Intent routing semantic projection",
        "goal": "Replace lexical IntentMatcher classification with one atomic IntentProjection adapter.",
        "dependencies": ["FW-10", "FW-11"],
        "risk": "BLOCKER",
        "difficulty": "HIGH",
        "rollback": "Run complete Legacy intent routing for the turn before ActionPlanner.",
        "acceptance": "Intent, flow, mission, and execution-plan parity meet routing promotion thresholds.",
        "disposition": "REPLACE_WITH_SEMANTIC",
    },
    "FW-13": {
        "name": "Kernel compiler structured input",
        "goal": "Compile Kernel programs from ExecutionPlan instead of classifying user text again.",
        "dependencies": ["FW-12"],
        "risk": "HIGH",
        "difficulty": "MEDIUM",
        "rollback": "Use the complete Legacy compiler result for the turn.",
        "acceptance": "Program and step-handler parity pass across RuntimeExecutor and Legacy validation.",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
    },
    "FW-14": {
        "name": "MissionManager structured input",
        "goal": "Keep mission authority while eliminating mission selection from free text.",
        "dependencies": ["FW-11", "FW-12"],
        "risk": "BLOCKER",
        "difficulty": "HIGH",
        "rollback": "Restore complete pre-turn mission state and execute Legacy mission selection.",
        "acceptance": "Mission selection, advancement, suspension, and resumption remain equivalent.",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
    },
    "FW-15": {
        "name": "Policy constrained semantic input",
        "goal": "Remove Policy text parsing while preserving Policy as an independent veto authority.",
        "dependencies": ["FW-12", "FW-14"],
        "risk": "BLOCKER",
        "difficulty": "HIGH",
        "rollback": "Fail closed or run the complete Legacy policy path; never merge policy outcomes.",
        "acceptance": "Safety parity is exact, adversarial unsafe-action recall is 100%, and fail-closed behavior is proven.",
        "disposition": "REPLACE_WITH_STRUCTURED_INPUT",
    },
    "FW-16": {
        "name": "Firewall enforcement and compatibility quarantine",
        "goal": "Make any unallowlisted downstream free-text read fail static validation.",
        "dependencies": [
            "FW-2", "FW-3", "FW-4", "FW-5", "FW-6", "FW-7", "FW-8",
            "FW-9", "FW-10", "FW-11", "FW-12", "FW-13", "FW-14", "FW-15",
        ],
        "risk": "MEDIUM",
        "difficulty": "LOW",
        "rollback": "Disable enforcement while retaining the inventory report.",
        "acceptance": "Zero unallowlisted reads; only capture, SemanticAuthority, audit, and constrained output remain.",
        "disposition": "ENFORCE",
    },
}


_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "BLOCKER": 3}


def build_semantic_firewall_refactoring_plan(
    repository_root: str | Path | None = None,
) -> SemanticFirewallRefactoringPlan:
    graph = build_authority_dependency_graph(repository_root)
    inventory = _build_inventory(graph.semantic_firewall_audit)
    replacement_matrix = _replacement_matrix(inventory)
    packages = _build_packages(inventory, graph.promotion_readiness)
    elimination_order = _order_packages(packages)
    recomputation_report = _build_recomputation_report(
        graph.recomputation_audit,
        graph.edges,
        inventory,
    )
    collapse_candidates = _dependency_collapse_candidates(inventory)
    promotion_forecast = _promotion_forecast(elimination_order, packages, inventory)
    summary = _summary(inventory, packages, collapse_candidates, recomputation_report)
    payload = {
        "authority_source_hash": graph.source_hash,
        "authority_graph_hash": graph.graph_hash,
        "inventory": inventory,
        "replacement_matrix": replacement_matrix,
        "migration_packages": packages,
        "elimination_order": elimination_order,
        "recomputation_report": recomputation_report,
        "dependency_collapse_candidates": collapse_candidates,
        "promotion_forecast": promotion_forecast,
        "summary": summary,
    }
    return SemanticFirewallRefactoringPlan(
        repository_root=graph.repository_root,
        authority_source_hash=graph.source_hash,
        authority_graph_hash=graph.graph_hash,
        inventory=tuple(inventory),
        replacement_matrix=tuple(replacement_matrix),
        migration_packages=tuple(packages),
        elimination_order=tuple(elimination_order),
        recomputation_report=recomputation_report,
        dependency_collapse_candidates=tuple(collapse_candidates),
        promotion_forecast=tuple(promotion_forecast),
        summary=summary,
        plan_hash=_stable_hash(payload),
    )


def select_first_eligible_migration_package(
    plan: SemanticFirewallRefactoringPlan,
    *,
    prohibited_components: Sequence[str] = (),
) -> dict[str, Any]:
    prohibited = set(prohibited_components)
    package_by_id = {item["package_id"]: item for item in plan.migration_packages}
    forecast_by_id = {
        item["after_package"]: item for item in plan.promotion_forecast
    }
    evaluated: list[dict[str, Any]] = []
    for ordered in plan.elimination_order:
        package_id = str(ordered["package_id"])
        package = package_by_id[package_id]
        authority_statuses = {
            str(item["status"]) for item in package.get("authority_readiness") or []
        }
        readiness = (
            "READY"
            if "READY" in authority_statuses
            else "LOW_RISK"
            if package["risk"] == "LOW"
            and package["disposition"] not in {"KEEP_ALLOWED", "KEEP_CONSTRAINED"}
            else "NOT_ELIGIBLE"
        )
        blocked_components = sorted(prohibited & set(package["components"]))
        if package["disposition"] == "KEEP_ALLOWED":
            reason = "allowlist_baseline_not_a_migration"
        elif blocked_components:
            reason = "component_prohibited_by_rc"
        elif package["risk"] in {"HIGH", "BLOCKER"}:
            reason = "high_risk_package_forbidden"
        elif readiness not in {"READY", "LOW_RISK"}:
            reason = "not_ready_or_low_risk"
        else:
            reason = "selected"
        record = {
            "position": ordered["position"],
            "package_id": package_id,
            "name": package["name"],
            "risk": package["risk"],
            "readiness": readiness,
            "disposition": package["disposition"],
            "components": list(package["components"]),
            "blocked_components": blocked_components,
            "forecast_status": forecast_by_id[package_id]["forecast_status"],
            "selection_reason": reason,
        }
        evaluated.append(record)
        if reason == "selected":
            return {
                "contract": "semantic_firewall_package_selection.v1",
                "source_plan_hash": plan.plan_hash,
                "selection_policy": (
                    "masterplan_order_then_ready_or_low_risk_then_rc_component_constraints"
                ),
                "selected": record,
                "evaluated_before_selection": evaluated,
                "document_name": (
                    "ACA-101_FW2_" + _document_slug(str(package["name"])) + ".md"
                ),
            }
    raise RuntimeError("No READY or LOW_RISK semantic firewall package is deployable")


def _build_inventory(audit: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, source in enumerate(audit, start=1):
        item = dict(source)
        is_violation = item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
        allowed = not is_violation
        profile = _allowed_profile(item) if allowed else _replacement_profile(item)
        access_mode, access_roles = _access_classification(item)
        severity = (
            "COMPATIBILITY"
            if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS"
            else "ALLOWED"
            if allowed
            else _severity(str(item["severity"]))
        )
        consumer_id = (
            f"TXT-{index:03d}:{item['file']}:{item['function']}:{item['line']}"
        )
        output.append(
            {
                "consumer_id": consumer_id,
                "classification": item["classification"],
                "severity": severity,
                "file": item["file"],
                "function": item["function"],
                "line": item["line"],
                "component": item["component"],
                "artifact": item["artifact"],
                "phase": item["phase"],
                "source_kind": item["source_kind"],
                "expression": item["expression"],
                "source_line": item["source_line"],
                "access_mode": access_mode,
                "access_roles": access_roles,
                "why_text_is_read": item["purpose"],
                "information_obtained": profile["information_used"],
                "semantic_replacement_source": profile["replacement_source"],
                "semantic_replacement_field": profile["replacement_field"],
                "replacement_status": profile["replacement_status"],
                "disposition": profile["disposition"],
                "target_access": profile["target_access"],
                "migration_package": profile["package_id"],
                "migration_cost": _migration_cost(item, profile),
                "functional_risk": _functional_risk(item, allowed),
                "cognitive_risk": _cognitive_risk(item, allowed),
                "rollback": _consumer_rollback(item, profile, allowed),
                "promotion_impact": profile["promotion_impact"],
                "can_remove_consumer": _can_remove_consumer(item),
            }
        )
    return output


def _allowed_profile(item: Mapping[str, Any]) -> dict[str, str]:
    component = str(item["component"])
    if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS":
        return {
            "information_used": "Independent Legacy conversational-act candidate for diff and rollback.",
            "replacement_source": "Pre-firewall Legacy compatibility lane",
            "replacement_field": "legacy_conversational_act_candidate",
            "replacement_status": "MIGRATED_OUT_OF_DOWNSTREAM_FIREWALL",
            "disposition": "KEEP_PREFIREWALL_LEGACY_ROLLBACK",
            "target_access": (
                "May interpret text only before SemanticAuthority and may expose only a complete immutable candidate downstream."
            ),
            "package_id": "FW-4",
            "promotion_impact": (
                "ConversationalAct is downstream-firewall-clean while Legacy remains atomic rollback."
            ),
        }
    if component == "semantic_authority":
        purpose = "Single authorized construction of SemanticRepresentation."
        target = "UserTurn.raw_text at the firewall ingress only."
    elif component == "conversation_manager":
        purpose = "Pre-semantic capture of the immutable user turn."
        target = "Transport/session capture before SemanticAuthority."
    else:
        purpose = "Audit or session serialization without interpretation."
        target = "Redacted immutable audit envelope."
    return {
        "information_used": purpose,
        "replacement_source": "Original user turn",
        "replacement_field": target,
        "replacement_status": "ALLOWLISTED_NON_COGNITIVE_ACCESS",
        "disposition": "KEEP_ALLOWED",
        "target_access": "May store or serialize text; must not derive cognitive artifacts.",
        "package_id": "FW-A0",
        "promotion_impact": "No promotion; preserves transport, semantic ingress, and audit evidence.",
    }


def _replacement_profile(item: Mapping[str, Any]) -> dict[str, str]:
    artifact = str(item["artifact"])
    profile = _REPLACEMENTS.get(artifact)
    if profile is None:
        raise ValueError(
            f"No semantic firewall replacement for {artifact} at "
            f"{item['file']}:{item['line']}"
        )
    return profile


def _access_classification(item: Mapping[str, Any]) -> tuple[str, list[str]]:
    component = str(item["component"])
    function = str(item["function"])
    source_line = str(item["source_line"])
    roles = ["read"]
    if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS":
        return "comparison", ["comparison", "fallback", "read"]
    if item["classification"] == "ALLOWED_TEXT_ACCESS":
        if component in {"runtime_timeline", "session"}:
            return "audit", ["audit", "read"]
        if component == "conversation_manager":
            return "write", ["write", "read"]
        return "read", ["read"]
    if component == "operational_work_mapper":
        return "fallback", ["fallback", "read"]
    if function == "Observe.execute" and "=" in source_line:
        return "write", ["write", "read", "recomputation"]
    if item["file"] == "aca_os/runtime.py" and 473 <= int(item["line"]) <= 476:
        return "recomputation", ["recomputation", "read", "write"]
    if component == "plugin_semantic":
        return "recomputation", ["recomputation", "read", "comparison"]
    if component == "conversation_state" or str(item["source_kind"]) == "free_text_parameter":
        return "recomputation", ["recomputation", "read"]
    if str(item["artifact"]) == "conversational_act":
        roles.extend(["fallback", "comparison"])
    return "read", sorted(set(roles))


def _severity(value: str) -> str:
    return {
        "critical": "BLOCKER",
        "high": "HIGH",
        "medium": "MEDIUM",
        "low": "LOW",
        "none": "ALLOWED",
    }[value]


def _migration_cost(item: Mapping[str, Any], profile: Mapping[str, str]) -> str:
    if profile["disposition"] in {"KEEP_ALLOWED", "KEEP_CONSTRAINED"}:
        return "LOW"
    if item["impact"] in {"shadow_only", "output_only"}:
        return "LOW"
    if item["artifact"] in {
        "conversational_act", "topic_state", "conversational_goal", "slot_state",
    }:
        return "MEDIUM"
    return "HIGH"


def _functional_risk(item: Mapping[str, Any], allowed: bool) -> str:
    if allowed:
        return "LOW"
    if item["impact"] in {"safety_decision", "mission_selection", "routing_and_planning"}:
        return "BLOCKER"
    if item["impact"] in {"planning_input", "cognitive_execution", "state_or_decision"}:
        return "HIGH"
    return "LOW" if item["impact"] == "output_only" else "MEDIUM"


def _cognitive_risk(item: Mapping[str, Any], allowed: bool) -> str:
    if allowed or item["impact"] in {"observability", "output_only", "shadow_only"}:
        return "LOW"
    if item["impact"] in {"safety_decision", "routing_and_planning", "mission_selection"}:
        return "BLOCKER"
    return "HIGH"


def _consumer_rollback(
    item: Mapping[str, Any],
    profile: Mapping[str, str],
    allowed: bool,
) -> str:
    if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS":
        return (
            "Select the complete pre-firewall Legacy candidate for the turn; never merge fields."
        )
    if allowed:
        return "No migration rollback; keep the access allowlisted and non-cognitive."
    if profile["disposition"] == "KEEP_CONSTRAINED":
        return "Restore the current output-only envelope; no state rollback is required."
    if item["impact"] == "shadow_only":
        return "Restore the Shadow text fallback; visible behavior remains unchanged."
    if item["artifact"] == "policy_result":
        return "Fail closed or select the complete Legacy policy result for the turn."
    return "Select the complete Legacy artifact for the turn; never merge Legacy and Semantic fields."


def _can_remove_consumer(item: Mapping[str, Any]) -> str:
    component = str(item["component"])
    file = str(item["file"])
    line = int(item["line"])
    if component == "operational_work_mapper":
        return "REMOVE_TEXT_FALLBACK_ONLY"
    if component == "plugin_semantic":
        return "COLLAPSE_DUPLICATE_PARSER_AFTER_PARITY"
    if file == "aca_os/runtime.py" and 473 <= line <= 476:
        return "REMOVE_DUPLICATE_WRITE_AFTER_FW_11"
    if component == "intent_matcher":
        return "COLLAPSE_TO_COMPATIBILITY_ADAPTER_AFTER_FW_12"
    if component == "kernel" and item["artifact"] in {"kernel_entities", "conversation_facts"}:
        return "REMOVE_DUPLICATE_INTERPRETATION_AFTER_PARITY"
    return "KEEP_COMPONENT_REPLACE_INPUT"


def _replacement_matrix(inventory: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "consumer_id": item["consumer_id"],
            "text_source": item["source_kind"],
            "information_used": item["information_obtained"],
            "semantic_source": item["semantic_replacement_source"],
            "semantic_field": item["semantic_replacement_field"],
            "status": item["replacement_status"],
            "disposition": item["disposition"],
            "package_id": item["migration_package"],
        }
        for item in inventory
    ]


def _build_packages(
    inventory: Sequence[Mapping[str, Any]],
    authority_readiness: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    members: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in inventory:
        members[str(item["migration_package"])].append(item)
    packages: list[dict[str, Any]] = []
    readiness_by_artifact = {
        str(item["artifact"]): dict(item) for item in authority_readiness
    }
    for package_id, blueprint in _PACKAGE_BLUEPRINTS.items():
        package_members = members.get(package_id, [])
        packages.append(
            {
                "package_id": package_id,
                **blueprint,
                "consumer_count": len(package_members),
                "consumer_ids": [item["consumer_id"] for item in package_members],
                "components": sorted({str(item["component"]) for item in package_members})
                or list(blueprint.get("scope_components") or []),
                "artifacts": sorted({str(item["artifact"]) for item in package_members}),
                "authority_readiness": [
                    readiness_by_artifact[artifact]
                    for artifact in sorted({str(item["artifact"]) for item in package_members})
                    if artifact in readiness_by_artifact
                ],
                "source_locations": [
                    {
                        "file": item["file"],
                        "function": item["function"],
                        "line": item["line"],
                    }
                    for item in package_members
                ],
            }
        )
    return packages


def _order_packages(packages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item["package_id"]): item for item in packages}
    remaining = set(by_id)
    completed: set[str] = set()
    order: list[dict[str, Any]] = []
    while remaining:
        available = [
            package_id
            for package_id in remaining
            if set(by_id[package_id]["dependencies"]) <= completed
        ]
        if not available:
            unresolved = {key: by_id[key]["dependencies"] for key in sorted(remaining)}
            raise ValueError(f"Semantic firewall package dependency cycle: {unresolved}")
        available.sort(
            key=lambda package_id: (
                _RISK_ORDER[str(by_id[package_id]["risk"])],
                int(str(package_id).split("-")[-1]) if str(package_id).split("-")[-1].isdigit() else -1,
                package_id,
            )
        )
        selected = available[0]
        package = by_id[selected]
        order.append(
            {
                "position": len(order) + 1,
                "package_id": selected,
                "risk": package["risk"],
                "consumer_count": package["consumer_count"],
                "dependencies_satisfied": list(package["dependencies"]),
                "selection_reason": (
                    "Lowest-risk deployable package whose discovered dependencies are already satisfied."
                ),
                "acceptance": package["acceptance"],
            }
        )
        completed.add(selected)
        remaining.remove(selected)
    return order


def _build_recomputation_report(
    recomputations: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    inventory: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    text_consumers = {
        str(item["artifact"]): [
            candidate["consumer_id"]
            for candidate in inventory
            if candidate["artifact"] == item["artifact"]
        ]
        for item in recomputations
    }
    records = []
    for item in recomputations:
        artifact = str(item["artifact"])
        records.append(
            {
                **dict(item),
                "text_consumers": text_consumers.get(artifact, []),
                "migration_package": _recomputation_package(artifact),
                "collapse_action": _recomputation_action(artifact, str(item["type"])),
            }
        )
    relevant_artifacts = {str(item["artifact"]) for item in recomputations}
    relevant_edges = [
        dict(edge)
        for edge in edges
        if edge["source"] in relevant_artifacts or edge["target"] in relevant_artifacts
    ]
    lines = ["flowchart LR"]
    for edge in relevant_edges:
        source = _mermaid_id(str(edge["source"]))
        target = _mermaid_id(str(edge["target"]))
        label = f"{edge['producer']} / {edge['authority']}".replace('"', "'")
        lines.append(f'    {source}["{edge["source"]}"] -->|"{label}"| {target}["{edge["target"]}"]')
    return {
        "contract": "semantic_firewall_recomputation_report.v1",
        "record_count": len(records),
        "actual_overwrite_count": sum(
            item["type"] == "RECOMPUTED_AND_OVERWRITTEN" for item in records
        ),
        "records": records,
        "subgraph_edges": relevant_edges,
        "mermaid": "\n".join(dict.fromkeys(lines)),
    }


def _recomputation_package(artifact: str) -> str:
    if artifact in {
        "conversation_intent_model", "information_gain_plan", "conversation_plan",
        "conversation_response_plan",
    }:
        return "FW-11"
    if artifact == "conversational_act":
        return "FW-4"
    if artifact == "intent_match":
        return "FW-12"
    return "PRESERVE_MULTI_WRITER_LIFECYCLE"


def _recomputation_action(artifact: str, record_type: str) -> str:
    if record_type == "RECOMPUTED_AND_OVERWRITTEN":
        return "Collapse to one authoritative write after semantic inputs and rollback are complete."
    if artifact == "conversational_act":
        return "Preserve atomic selector until the Legacy pilot path is retired."
    if artifact == "intent_match":
        return "Replace multiple partial overrides with one complete authority result per turn."
    return "Preserve: multiple writers represent an expected state or execution lifecycle."


def _dependency_collapse_candidates(
    inventory: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates = (
        {
            "candidate": "Runtime post-Mission conversation planning block",
            "package_id": "FW-11",
            "current_responsibility": "Resolved (ACA-104): the pre-Mission ConversationManager.begin_turn write was removed; this block is now the single writer for CIM, InformationGainPlan, ConversationPlan, and ResponsePlan.",
            "replacement": "One structured planning chain after the authoritative state projection.",
            "removal_condition": "Exactly one writer and full plan/state parity.",
            "risk": "HIGH",
            "benefit": "Removed four overwrites and the principal blocker for CIM promotion.",
        },
        {
            "candidate": "OperationalWorkMapper._source_text fallback",
            "package_id": "FW-3",
            "current_responsibility": "Recovers raw text from three state snapshots for Shadow inference.",
            "replacement": "Semantic, state, plan, and execution projections already supplied to the mapper.",
            "removal_condition": "Operational benchmark parity without last_raw_payload.",
            "risk": "LOW",
            "benefit": "Removes three Shadow firewall violations.",
        },
        {
            "candidate": "Plugin-local semantic analyzers",
            "package_id": "FW-9",
            "current_responsibility": "Reparse free text for domain entities and hints.",
            "replacement": "Shared entity projection; plugin manifests provide domain vocabulary upstream.",
            "removal_condition": "Per-plugin entity and routing parity.",
            "risk": "HIGH",
            "benefit": "Eliminates parallel semantic authorities.",
        },
        {
            "candidate": "Kernel Extract text parser",
            "package_id": "FW-9",
            "current_responsibility": "Extracts entities from event.payload during Kernel execution.",
            "replacement": "Semantic entity projection copied into CognitiveState.",
            "removal_condition": "Kernel entity/provenance parity and atomic rollback.",
            "risk": "HIGH",
            "benefit": "Removes a second entity extractor from the cognitive loop.",
        },
        {
            "candidate": "IntentMatcher lexical implementation",
            "package_id": "FW-12",
            "current_responsibility": "Classifies the utterance and feeds routing.",
            "replacement": "Compatibility adapter over SemanticProjection.intent_projection.",
            "removal_condition": "Intent, action, flow, and mission parity across official/adversarial suites.",
            "risk": "BLOCKER",
            "benefit": "Eliminates the dominant downstream text authority.",
        },
        {
            "candidate": "Kernel Observe.last_raw_payload cognitive fact",
            "package_id": "FW-8",
            "current_responsibility": "Stores raw input inside cognitive facts.",
            "replacement": "Typed assertions/events plus audit reference outside cognitive facts.",
            "removal_condition": "Fact, replay, trace, and output-grounding consumers no longer read it.",
            "risk": "HIGH",
            "benefit": "Separates audit evidence from cognitive state.",
        },
        {
            "candidate": "Duplicated /demo/domain-flow conversation pipeline",
            "package_id": "PARALLEL_PIPELINE_RETIREMENT",
            "current_responsibility": (
                "Interprets message aliases in DemoDomainRuntimeFlowRunner, PublicConversationWorkflow, "
                "PublicConversationState, and RepresentativeAnswerComposer outside the official Runtime firewall."
            ),
            "replacement": "The official ACAOSRuntime pipeline and its public presentation adapter.",
            "removal_condition": (
                "The demo endpoint is removed or delegated to the official Runtime with API/test parity."
            ),
            "risk": "MEDIUM",
            "benefit": (
                "Eliminates an entire parallel text authority instead of migrating its internal reads."
            ),
        },
    )
    live_locations = {
        (str(item["file"]), str(item["function"])) for item in inventory
    }
    filtered = []
    for item in candidates:
        if item["package_id"] == "FW-3" and not any(
            file == "aca_os/operational_work_mapper.py" for file, _ in live_locations
        ):
            continue
        filtered.append(dict(item))
    return filtered


def _promotion_forecast(
    order: Sequence[Mapping[str, Any]],
    packages: Sequence[Mapping[str, Any]],
    inventory: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    package_by_id = {str(item["package_id"]): item for item in packages}
    forecasts = {
        "FW-A0": ([], "NO_CHANGE", "Defines legal ingress and audit boundaries."),
        "FW-2": ([], "NO_CHANGE", "Output realization remains non-authoritative."),
        "FW-3": (["candidate_work"], "FIREWALL_CLEAN_SHADOW", "No cognitive promotion."),
        "FW-4": (["conversational_act"], "FULL_PROMOTION_ELIGIBLE", "Subject to pilot thresholds."),
        "FW-5": (["conversational_goal"], "PILOT_ELIGIBLE", "Lowest-coupling mutable state candidate."),
        "FW-6": (["topic_state"], "PILOT_ELIGIBLE", "Topic rollback must restore the full stack."),
        "FW-7": (["slot_state"], "PILOT_ELIGIBLE", "Slot and pending-question rollback must be atomic."),
        "FW-8": (["conversation_facts"], "PILOT_ELIGIBLE", "Fact history and mission snapshot must roll back together."),
        "FW-9": (["kernel_entities"], "PILOT_ELIGIBLE", "Plugin parity is mandatory."),
        "FW-10": (["conversation_intent_model"], "UNBLOCKED_NOT_READY", "Duplicate Runtime writer resolved (ACA-104); two critical free-text reads remain."),
        "FW-11": (["conversation_intent_model"], "PILOT_ELIGIBLE", "CIM has one structured writer; plans remain derived."),
        "FW-12": (["intent_match"], "PILOT_ELIGIBLE_HIGH_RISK", "Routing rollback must occur before ActionPlanner."),
        "FW-13": (["kernel_program"], "FIREWALL_CLEAN_DERIVED", "Never a semantic authority target."),
        "FW-14": (["mission"], "FIREWALL_CLEAN_INDEPENDENT", "MissionManager retains mission authority."),
        "FW-15": (["policy_result"], "FIREWALL_CLEAN_INDEPENDENT", "Policy retains veto authority and fail-closed behavior."),
        "FW-16": ([], "SA_4_ENTRY_CRITERIA_MET", "Zero unallowlisted cognitive reads remain."),
    }
    output = []
    for item in order:
        package_id = str(item["package_id"])
        artifacts, status, reason = forecasts[package_id]
        members = [
            entry["consumer_id"]
            for entry in inventory
            if entry["migration_package"] == package_id
        ]
        output.append(
            {
                "after_position": item["position"],
                "after_package": package_id,
                "consumers_resolved": members,
                "artifacts_affected": artifacts,
                "forecast_status": status,
                "reason": reason,
                "package_name": package_by_id[package_id]["name"],
            }
        )
    return output


def _summary(
    inventory: Sequence[Mapping[str, Any]],
    packages: Sequence[Mapping[str, Any]],
    collapse_candidates: Sequence[Mapping[str, Any]],
    recomputation_report: Mapping[str, Any],
) -> dict[str, Any]:
    violations = [
        item
        for item in inventory
        if item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
    ]
    allowed = [
        item for item in inventory if item["classification"] == "ALLOWED_TEXT_ACCESS"
    ]
    compatibility = [
        item
        for item in inventory
        if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS"
    ]
    role_counts = Counter(
        role for item in inventory for role in item["access_roles"]
    )
    access_role_distribution = {
        role: role_counts[role]
        for role in (
            "read", "write", "recomputation", "fallback", "audit", "debug", "comparison"
        )
    }
    return {
        "text_access_count": len(inventory),
        "allowed_access_count": len(allowed),
        "legacy_prefirewall_compatibility_count": len(compatibility),
        "violation_count": len(violations),
        "severity_distribution": dict(sorted(Counter(item["severity"] for item in violations).items())),
        "access_mode_distribution": dict(sorted(Counter(item["access_mode"] for item in inventory).items())),
        "access_role_distribution": access_role_distribution,
        "replacement_coverage": round(
            sum(bool(item["semantic_replacement_field"]) for item in inventory) / len(inventory),
            4,
        ),
        "package_count": len(packages),
        "recomputation_count": int(recomputation_report["record_count"]),
        "actual_overwrite_count": int(recomputation_report["actual_overwrite_count"]),
        "collapse_candidate_count": len(collapse_candidates),
        "sa4_blockers": sorted(
            {
                str(item["artifact"])
                for item in violations
                if item["severity"] == "BLOCKER"
            }
        ),
        "effective_authority": "legacy",
        "behavior_change": False,
        "inventory_scope": (
            "Official ACAOSRuntime/Studio authority graph; duplicated /demo/domain-flow is tracked "
            "as a collapse candidate rather than migrated consumer-by-consumer."
        ),
    }


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mermaid_id(value: str) -> str:
    return "N_" + "".join(character if character.isalnum() else "_" for character in value)


def _document_slug(value: str) -> str:
    words = [word for word in value.replace("-", " ").split() if word]
    return "_".join(words)
