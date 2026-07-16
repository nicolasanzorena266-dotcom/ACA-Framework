from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping, Sequence

from aca_core.text import normalize_text


OPERATIONAL_OUTCOMES = {
    "completed",
    "prepared",
    "blocked",
    "delegated",
    "explained",
    "waiting_for_user",
    "waiting_for_system",
    "unsafe_operation",
    "no_action_required",
}


def map_operational_work(
    state_snapshot: Mapping[str, Any],
    *,
    plugin_manifests: Sequence[Mapping[str, Any]] = (),
    tool_contracts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project existing cognitive/runtime state into passive operational work.

    The mapper is intentionally side-effect free: it never mutates the incoming
    state, never calls tools and never decides the user-facing response.
    """

    facts = _facts_from_snapshot(state_snapshot)
    response_plan = _payload_from_trace(facts.get("conversation_response_plan"), "plan")
    intent_model = _payload_from_trace(facts.get("conversation_intent_model"), "model")
    information_gain_plan = _payload_from_trace(facts.get("conversation_information_gain_plan"), "plan")
    conversation_plan = _payload_from_trace(facts.get("conversation_plan"), "plan")
    fulfillment = _payload_from_trace(facts.get("conversation_fulfillment"), "fulfillment")
    execution_plan = _mapping(facts.get("zero_cost_execution_plan"))
    policy = _policy_from_snapshot(state_snapshot, facts)
    runtime_engine = _mapping(facts.get("runtime_execution_engine"))
    outcomes = list(facts.get("execution_step_outcomes") or [])
    runtime_record = _mapping(facts.get("conversation_state_runtime"))
    final_conversation_state = _mapping(runtime_record.get("final_state"))
    tool_contracts = dict(tool_contracts or {})

    source_selection = _source_text(
        response_plan,
        intent_model,
        runtime_record,
        state_snapshot,
    )
    source_text = str(source_selection["text"])
    normalized_text = normalize_text(source_text)
    operation = _select_operation(
        normalized_text=normalized_text,
        response_plan=response_plan,
        intent_model=intent_model,
        information_gain_plan=information_gain_plan,
        conversation_plan=conversation_plan,
        fulfillment=fulfillment,
        execution_plan=execution_plan,
        policy=policy,
    )
    category = _category_for_operation(operation)
    outcome = _outcome_for_operation(
        operation=operation,
        category=category,
        normalized_text=normalized_text,
        information_gain_plan=information_gain_plan,
        fulfillment=fulfillment,
        execution_plan=execution_plan,
        policy=policy,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
    )
    blocked_by = _blocked_by(
        operation=operation,
        outcome=outcome,
        normalized_text=normalized_text,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
        policy=policy,
    )
    required_information = _required_information(
        information_gain_plan=information_gain_plan,
        response_plan=response_plan,
        conversation_plan=conversation_plan,
    )
    available_tools = _available_tools(plugin_manifests=plugin_manifests, tool_contracts=tool_contracts)
    candidate_work = _candidate_work(
        operation=operation,
        category=category,
        outcome=outcome,
        normalized_text=normalized_text,
        response_plan=response_plan,
        information_gain_plan=information_gain_plan,
        conversation_plan=conversation_plan,
        fulfillment=fulfillment,
        execution_plan=execution_plan,
        policy=policy,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
        blocked_by=blocked_by,
    )
    case_state_projection = _case_state_projection(
        normalized_text=normalized_text,
        final_conversation_state=final_conversation_state,
        conversation_plan=conversation_plan,
        fulfillment=fulfillment,
        execution_plan=execution_plan,
        runtime_outcomes=outcomes,
        candidate_work=candidate_work,
        required_information=required_information,
    )
    case_state_projected_ranking = _case_state_projected_ranking(
        candidate_work=candidate_work,
        case_state_projection=case_state_projection,
    )
    ranked_primary = _mapping(candidate_work[0]) if candidate_work else {}
    confidence = _confidence(
        operation=operation,
        response_plan=response_plan,
        execution_plan=execution_plan,
        policy=policy,
        normalized_text=normalized_text,
    )
    impossible = _suggests_impossible_work(
        operation=operation,
        outcome=outcome,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
    )

    mapping = {
        "contract": "operational_work_shadow.v1",
        "component": "operational_work_mapper",
        "mode": "shadow",
        "passive": True,
        "mutates_state": False,
        "changes_response": False,
        "role": _role_from_state(final_conversation_state, execution_plan, normalized_text),
        "responsibility": _responsibility_for_operation(operation),
        "candidate_work": candidate_work,
        "case_state_projection": case_state_projection,
        "case_state_projected_ranking": case_state_projected_ranking,
        "selected_work": {
            "operation": operation,
            "category": category,
            "expected_outcome": outcome,
            "confidence": confidence,
            "rank": ranked_primary.get("rank", 1),
            "priority": ranked_primary.get("priority"),
            "status": ranked_primary.get("status"),
        },
        "expected_outcome": outcome,
        "operational_category": category,
        "required_information": required_information,
        "available_tools": available_tools,
        "blocked_by": blocked_by,
        "impossible_work_suggested": impossible,
        "operational_value": _operational_value(outcome, impossible=impossible),
        "confidence": confidence,
        "coherence": {
            "conversation_plan": _conversation_plan_coherence(operation, conversation_plan),
            "execution_plan": _execution_plan_coherence(operation, execution_plan),
            "policy": _policy_coherence(policy),
        },
        "observed_inputs": {
            "conversation_state": bool(final_conversation_state),
            "conversation_plan": bool(conversation_plan),
            "conversation_response_plan": bool(response_plan),
            "conversation_fulfillment": bool(fulfillment),
            "execution_plan": bool(execution_plan),
            "policy": bool(policy),
            "runtime_outcomes": len(outcomes),
            "plugin_manifest_count": len(plugin_manifests),
            "tool_contract_count": len(tool_contracts),
            "semantic_projection": bool(source_selection["semantic_available"]),
        },
        "evidence": {
            "primary_user_need": deepcopy(_mapping(response_plan.get("primary_user_need"))),
            "dominant_concern": deepcopy(_mapping(response_plan.get("dominant_concern"))),
            "runtime_flow": execution_plan.get("flow") or runtime_engine.get("flow"),
            "kernel_program": execution_plan.get("kernel_program") or runtime_engine.get("kernel_program"),
            "policy_decision": policy.get("decision"),
            "source_text_available": bool(source_text),
        },
        "semantic_firewall": {
            "contract": "candidate_work_semantic_firewall.v1",
            "package": "FW-3",
            "authority_mode": source_selection["authority_mode"],
            "authority_reason": source_selection["authority_reason"],
            "semantic_usage": source_selection["authority_mode"] == "semantic",
            "legacy_usage": source_selection["authority_mode"] in {"legacy", "rollback"},
            "rollback": source_selection["authority_mode"] == "rollback",
            "legacy_available": source_selection["legacy_available"],
            "semantic_available": source_selection["semantic_available"],
            "agreement_rate": source_selection["agreement_rate"],
            "confidence": source_selection["confidence"],
            "failure_reason": source_selection["failure_reason"],
            "selected_source": source_selection["selected_source"],
            "source_hash": source_selection["source_hash"],
            "mixed_authority": False,
            "downstream_raw_payload_access": False,
        },
        "candidate_summary": _candidate_summary(candidate_work),
    }
    return mapping


def compare_operational_work_to_expected(
    mapped_work: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    selected = _mapping(mapped_work.get("selected_work"))
    expected_operation = str(expected.get("expected_operation") or "")
    expected_category = str(expected.get("expected_category") or "")
    expected_outcome = str(expected.get("expected_outcome") or "")
    actual_operation = str(selected.get("operation") or "")
    actual_category = str(selected.get("category") or mapped_work.get("operational_category") or "")
    actual_outcome = str(selected.get("expected_outcome") or mapped_work.get("expected_outcome") or "")
    outcome_options = {
        item.strip()
        for item in expected_outcome.split("|")
        if item.strip()
    } or {expected_outcome}
    operation_match = _operation_matches(actual_operation, expected_operation)
    category_match = actual_category == expected_category if expected_category else False
    outcome_match = actual_outcome in outcome_options
    impossible = bool(mapped_work.get("impossible_work_suggested"))
    if "impossible_work_suggested" not in mapped_work:
        impossible = _suggests_impossible_work(
            operation=actual_operation,
            outcome=actual_outcome,
            plugin_manifests=(),
            tool_contracts={},
        )
    score = (
        int(operation_match)
        + int(category_match)
        + int(outcome_match)
        - int(impossible)
    )
    return {
        "operation_match": operation_match,
        "category_match": category_match,
        "outcome_match": outcome_match,
        "expected_operation": expected_operation,
        "actual_operation": actual_operation,
        "expected_category": expected_category,
        "actual_category": actual_category,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "impossible_work_suggested": impossible,
        "score": max(score, 0),
        "max_score": 3,
    }


def _facts_from_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    facts = snapshot.get("facts") if isinstance(snapshot, Mapping) else {}
    return dict(facts) if isinstance(facts, Mapping) else dict(snapshot)


def _payload_from_trace(value: Any, payload_key: str) -> dict[str, Any]:
    trace = _mapping(value)
    payload = trace.get(payload_key)
    if isinstance(payload, Mapping):
        return dict(payload)
    return trace


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _policy_from_snapshot(snapshot: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    policy = snapshot.get("policy_result") if isinstance(snapshot, Mapping) else None
    if isinstance(policy, Mapping):
        return dict(policy)
    authority = _mapping(facts.get("runtime_execution_authority"))
    evaluation = _mapping(authority.get("policy_evaluation"))
    if evaluation:
        evaluation["decision"] = authority.get("policy_decision")
        return evaluation
    outcomes = list(facts.get("execution_step_outcomes") or [])
    for outcome in outcomes:
        item = _mapping(outcome)
        if item.get("step") == "policy":
            return _mapping(item.get("result"))
    return {}


def _source_text(
    response_plan: Mapping[str, Any],
    intent_model: Mapping[str, Any],
    runtime_record: Mapping[str, Any],
    state_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    legacy_sources = (
        _mapping(intent_model.get("evidence")).get("message"),
        _mapping(_mapping(intent_model.get("response_objective")).get("evidence")).get("normalized_message"),
        _mapping(response_plan.get("evidence")).get("message"),
        _mapping(_mapping(response_plan.get("primary_user_need")).get("evidence")).get("text"),
    )
    legacy_text = ""
    for source in legacy_sources:
        if source:
            legacy_text = str(source)
            break

    semantic_projection = _semantic_projection_from_runtime(runtime_record)
    semantic_text = _semantic_projection_signal(semantic_projection)
    rollback_text = str(state_snapshot.get("response") or "")

    if legacy_text:
        selected_text = legacy_text
        authority_mode = "legacy"
        authority_reason = "structured_legacy_plan_available"
        selected_source = "conversation_planning_projection"
        failure_reason = None
        confidence = 1.0
    elif semantic_text:
        selected_text = semantic_text
        authority_mode = "semantic"
        authority_reason = "semantic_projection_replaced_raw_payload_fallback"
        selected_source = "semantic_projection"
        failure_reason = None
        confidence = _semantic_projection_confidence(semantic_projection)
    elif rollback_text:
        selected_text = rollback_text
        authority_mode = "rollback"
        authority_reason = "semantic_projection_unavailable_legacy_output_rollback"
        selected_source = "legacy_output"
        failure_reason = "semantic_projection_unavailable"
        confidence = 0.5
    else:
        selected_text = ""
        authority_mode = "rollback"
        authority_reason = "no_candidate_work_source_available"
        selected_source = "none"
        failure_reason = "semantic_and_legacy_sources_unavailable"
        confidence = 0.0

    return {
        "text": selected_text,
        "authority_mode": authority_mode,
        "authority_reason": authority_reason,
        "selected_source": selected_source,
        "legacy_available": bool(legacy_text or rollback_text),
        "semantic_available": bool(semantic_text),
        "agreement_rate": _source_agreement(legacy_text, semantic_text),
        "confidence": confidence,
        "failure_reason": failure_reason,
        "source_hash": hashlib.sha256(selected_text.encode("utf-8")).hexdigest(),
    }


def _semantic_projection_from_runtime(runtime_record: Mapping[str, Any]) -> dict[str, Any]:
    shadow = _mapping(runtime_record.get("semantic_projection_shadow"))
    projection = _mapping(shadow.get("semantic_projection"))
    if projection.get("contract") != "semantic_projection.v1":
        return {}
    return projection


def _semantic_projection_signal(projection: Mapping[str, Any]) -> str:
    if not projection:
        return ""

    signals: list[str] = []
    intent_projection = _mapping(projection.get("intent_projection"))
    selected_intent = _mapping(intent_projection.get("selected"))
    _append_semantic_signal(signals, selected_intent.get("intent"))
    for candidate in intent_projection.get("candidates") or []:
        _append_semantic_signal(signals, _mapping(candidate).get("intent"))

    topic_projection = _mapping(projection.get("topic_projection"))
    for topic in topic_projection.get("topics") or []:
        _append_semantic_signal(signals, _mapping(topic).get("type"))

    goal_projection = _mapping(projection.get("goal_projection"))
    for goal in goal_projection.get("goals") or []:
        item = _mapping(goal)
        _append_semantic_signal(signals, item.get("type"))
        _append_semantic_signal(signals, item.get("target"))

    fact_projection = _mapping(projection.get("fact_projection"))
    for fact in fact_projection.get("items") or []:
        item = _mapping(fact)
        _append_semantic_signal(signals, item.get("predicate"))
        value = item.get("value")
        if isinstance(value, (str, int, float, bool)):
            _append_semantic_signal(signals, value)

    entity_projection = _mapping(projection.get("entity_projection"))
    for entity in entity_projection.get("items") or []:
        item = _mapping(entity)
        _append_semantic_signal(signals, item.get("type"))
        _append_semantic_signal(signals, item.get("value"))

    return " ".join(dict.fromkeys(signals))


def _append_semantic_signal(signals: list[str], value: Any) -> None:
    signal = normalize_text(str(value or "").replace("_", " "))
    if signal:
        signals.append(signal)


def _semantic_projection_confidence(projection: Mapping[str, Any]) -> float:
    selected = _mapping(_mapping(projection.get("intent_projection")).get("selected"))
    try:
        return max(0.0, min(1.0, float(selected.get("confidence") or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _source_agreement(legacy_text: str, semantic_text: str) -> float:
    legacy_tokens = set(normalize_text(legacy_text).split())
    semantic_tokens = set(normalize_text(semantic_text).split())
    if not legacy_tokens or not semantic_tokens:
        return 0.0
    return round(len(legacy_tokens & semantic_tokens) / len(legacy_tokens | semantic_tokens), 4)


def _select_operation(
    *,
    normalized_text: str,
    response_plan: Mapping[str, Any],
    intent_model: Mapping[str, Any],
    information_gain_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> str:
    primary_key = str(_mapping(response_plan.get("primary_user_need")).get("key") or "")
    concern_key = str(_mapping(response_plan.get("dominant_concern")).get("key") or "")
    flow = str(execution_plan.get("flow") or "")
    program = str(execution_plan.get("kernel_program") or "")
    policy_decision = str(policy.get("decision") or "")

    if _has_any(normalized_text, ("ya te lo dije", "nunca dije", "no me estas ayudando")):
        return "repair_service_interaction"
    if _has_any(normalized_text, ("consulta mi expediente", "consultar expediente", "estado real", "ver mi expediente")):
        return "block_real_status_lookup"
    if _has_any(normalized_text, ("te mando los documentos", "subir documentos", "cargar documentos por aca", "upload")):
        return "block_document_upload"
    if _has_any(normalized_text, ("abrir el modem", "abrir modem", "desarmar el modem")):
        return "prevent_unsafe_technical_action"
    if _has_any(normalized_text, ("resumime", "resumen")):
        return "prepare_case_summary"
    if _has_any(normalized_text, ("explicamelo mas simple", "mas simple")):
        return "explain_current_step_simpler"
    if _has_any(normalized_text, ("rechazaron un documento", "rechazaron el documento", "documento rechazado")):
        return "request_rejection_detail"
    if _has_any(normalized_text, ("me llamen", "que me llamen", "llamenme", "callback")):
        return "prepare_handoff"
    if _has_any(normalized_text, ("legales", "legal")):
        return "prepare_handoff"
    if policy_decision in {"ESCALATE", "HANDOFF"} or "handoff" in flow or "representante" in normalized_text or "persona" in normalized_text or "supervisor" in normalized_text:
        return "prepare_handoff"
    if _has_any(normalized_text, ("dejemos la factura", "no importa la factura", "olvidate de la factura", "factura la vemos despues", "la factura la vemos despues", "ahora no tengo internet")) and _has_any(normalized_text, ("internet", "modem", "no funciona")):
        return "diagnose_connectivity_issue"
    if _has_any(normalized_text, ("no tengo internet", "sin internet")) and _has_any(normalized_text, ("factura", "vino mal")):
        return "continue_conversation_plan"
    if _has_any(normalized_text, ("volver a la denuncia", "volvamos a la denuncia", "sobre la denuncia")):
        return "collect_claim_blocker"
    if (
        _has_any(normalized_text, ("denuncia", "siniestro"))
        and _has_any(normalized_text, ("app", "nadie", "contact", "novedad", "seguimiento", "tramite"))
        and _has_any(normalized_text, ("puedo usar el auto", "arreglar el auto", "reparar el auto", "tocarlo antes", "tocar el auto", "mandarlo a reparar", "auto para trabajar"))
    ):
        return "prepare_claim_follow_up"
    if _has_any(normalized_text, ("puedo usar el auto", "arreglar el auto", "reparar el auto", "tocarlo antes", "tocar el auto", "mandarlo a reparar", "auto para trabajar", "mandar el auto al taller", "mandar auto al taller", "auto al taller")) or primary_key == "vehicle_repair_authorization" or concern_key == "vehicle_repair_authorization":
        return "provide_repair_risk_guidance"
    if _has_any(normalized_text, ("taller", "autorizacion")):
        return "prepare_claim_follow_up"
    if _has_any(normalized_text, ("cuanto tarda", "tarda normalmente", "cuanto demora", "demora normalmente")):
        return "explain_domain_concept"
    if _has_any(normalized_text, ("denuncia", "siniestro", "choque")) and _has_any(normalized_text, ("semana", "dias", "contact", "novedad", "tramite", "seguimiento", "nadie")):
        return "prepare_claim_follow_up"
    if _has_any(normalized_text, ("no hubo lesionados", "soy asegurado", "ya cargue la denuncia")) and _has_any(normalized_text, ("me chocaron", "choque", "denuncia")):
        return "collect_claim_blocker"
    if primary_key in {"claim_report_status", "claim_contact_progress", "claim_status_or_payment"}:
        return "prepare_claim_follow_up"
    if _has_any(normalized_text, ("factura", "cobraron", "cobro", "monto", "vencio", "vence", "150000", "11000")):
        return "prepare_billing_review" if not _has_any(normalized_text, ("por que", "porque")) else "request_billing_line_item"
    if _has_any(normalized_text, ("no tengo internet", "sin internet", "modem", "tecnico", "vecinos")):
        if _has_any(normalized_text, ("vecinos", "zona", "barrio")):
            return "prepare_outage_follow_up"
        if _has_any(normalized_text, ("tecnico", "reinicie", "sigue igual")):
            return "prepare_technical_visit"
        return "diagnose_connectivity_issue"
    if _has_any(normalized_text, ("reinicie todo", "sigue igual")):
        return "prepare_technical_visit"
    if _has_any(normalized_text, ("documentacion", "documentos", "fotos", "foto", "presupuesto", "cedula", "rechazaron")):
        if _has_any(normalized_text, ("rechazaron", "rechazado")):
            return "request_rejection_detail"
        if _has_any(normalized_text, ("tengo", "mande", "ya cargue", "ya mande")):
            return "prepare_documentation_review"
        return "explain_documentation_requirements"
    if _has_any(normalized_text, ("cleas", "franquicia", "cobertura", "cristal", "cristales")) or flow == "knowledge_lookup":
        return "explain_domain_concept"
    if _has_any(normalized_text, ("me chocaron", "choque", "siniestro")) or program == "auto_claim_guidance":
        selected_question = _mapping(information_gain_plan.get("selected_question"))
        if selected_question:
            return "collect_claim_blocker"
        return "start_claim_guidance"
    if _has_any(normalized_text, ("no funciona",)):
        return "continue_conversation_plan"
    if _has_any(normalized_text, ("dar de baja", "si no lo arreglan")):
        return "diagnose_connectivity_issue"
    if _has_any(normalized_text, ("gracias", "quedo claro", "listo")):
        return "close_case_no_action"
    fulfilled_goal = _mapping(fulfillment.get("fulfilled_goal"))
    if fulfilled_goal.get("satisfied"):
        return "explain_domain_concept"
    current_step = _mapping(_mapping(conversation_plan.get("active_plan")).get("current_step"))
    if current_step:
        return "continue_conversation_plan"
    return "no_operational_work_identified"


def _category_for_operation(operation: str) -> str:
    if operation in {
        "prepare_claim_follow_up",
        "prepare_billing_review",
        "prepare_outage_follow_up",
        "prepare_technical_visit",
        "prepare_documentation_review",
        "prepare_case_summary",
        "repair_service_interaction",
    }:
        return "preparatory"
    if operation in {
        "collect_claim_blocker",
        "request_billing_line_item",
        "request_rejection_detail",
        "diagnose_connectivity_issue",
        "continue_conversation_plan",
        "start_claim_guidance",
    }:
        return "administrative"
    if operation in {
        "explain_domain_concept",
        "explain_documentation_requirements",
        "explain_current_step_simpler",
    }:
        return "informative"
    if operation == "prepare_handoff":
        return "escalation"
    if operation in {
        "provide_repair_risk_guidance",
        "block_real_status_lookup",
        "block_document_upload",
        "prevent_unsafe_technical_action",
    }:
        return "protective"
    if operation == "close_case_no_action":
        return "administrative"
    return "none"


def _outcome_for_operation(
    *,
    operation: str,
    category: str,
    normalized_text: str,
    information_gain_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    policy: Mapping[str, Any],
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
) -> str:
    if operation in {"block_real_status_lookup", "block_document_upload"}:
        return "blocked"
    if operation in {"provide_repair_risk_guidance", "prevent_unsafe_technical_action"}:
        return "unsafe_operation"
    if operation == "prepare_handoff":
        return "delegated"
    if operation == "close_case_no_action":
        return "no_action_required"
    if operation == "prepare_technical_visit" and _has_any(normalized_text, ("viene el tecnico manana", "ya me dijeron que viene", "programado")):
        return "waiting_for_system"
    if operation in {"explain_domain_concept", "explain_documentation_requirements", "explain_current_step_simpler"}:
        return "explained"
    if operation in {"collect_claim_blocker", "request_billing_line_item", "request_rejection_detail", "diagnose_connectivity_issue", "continue_conversation_plan", "start_claim_guidance"}:
        return "waiting_for_user"
    if category == "preparatory":
        return "prepared"
    if _mapping(fulfillment.get("fulfilled_goal")).get("status") in {"fulfilled", "completed"}:
        return "explained"
    selected_question = _mapping(information_gain_plan.get("selected_question"))
    if selected_question:
        return "waiting_for_user"
    return "no_action_required" if operation == "no_operational_work_identified" else "prepared"


def _blocked_by(
    *,
    operation: str,
    outcome: str,
    normalized_text: str,
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    capability = _capability_for_operation(operation)
    if capability:
        action = _public_action_for_capability(plugin_manifests, capability)
        if action and not bool(action.get("enabled", False)):
            blockers.append(
                {
                    "type": "public_action_disabled",
                    "capability": capability,
                    "reason": action.get("disabled_reason") or "capability_disabled",
                }
            )
        if _capability_blocked(plugin_manifests, capability):
            blockers.append(
                {
                    "type": "blocked_capability",
                    "capability": capability,
                    "reason": "plugin_manifest_blocked_capability",
                }
            )
    if operation in {"block_real_status_lookup", "block_document_upload"} and not blockers:
        blockers.append(
            {
                "type": "missing_real_tool",
                "capability": capability or operation,
                "reason": "no_supported_tool_contract",
            }
        )
    if str(policy.get("decision") or "") in {"DENY", "ESCALATE"}:
        blockers.append(
            {
                "type": "policy",
                "decision": policy.get("decision"),
                "reason": policy.get("reason"),
            }
        )
    return blockers


def _required_information(
    *,
    information_gain_plan: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    required: list[dict[str, Any]] = []
    selected_question = _mapping(information_gain_plan.get("selected_question"))
    if selected_question:
        required.append(
            {
                "slot": selected_question.get("slot"),
                "question": selected_question.get("question"),
                "purpose": selected_question.get("purpose"),
                "affected_decisions": list(selected_question.get("affected_decisions") or []),
                "source": "information_gain_plan",
            }
        )
    for item in response_plan.get("required_information") or []:
        mapped = _mapping(item)
        if mapped:
            required.append(
                {
                    "slot": mapped.get("slot"),
                    "question": mapped.get("question"),
                    "purpose": mapped.get("purpose"),
                    "source": "conversation_response_plan",
                }
            )
    current_step = _mapping(_mapping(conversation_plan.get("active_plan")).get("current_step"))
    if current_step and current_step.get("status") == "pending" and current_step.get("slot"):
        required.append(
            {
                "slot": current_step.get("slot"),
                "question": None,
                "purpose": current_step.get("decision"),
                "source": "conversation_plan",
            }
        )
    return _unique_dicts(required)


def _candidate_work(
    *,
    operation: str,
    category: str,
    outcome: str,
    normalized_text: str,
    response_plan: Mapping[str, Any],
    information_gain_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    policy: Mapping[str, Any],
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
    blocked_by: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    primary = _mapping(response_plan.get("primary_user_need"))
    operations: list[dict[str, Any]] = [
        _operation_candidate(
            operation=operation,
            normalized_text=normalized_text,
            response_plan=response_plan,
            information_gain_plan=information_gain_plan,
            conversation_plan=conversation_plan,
            fulfillment=fulfillment,
            execution_plan=execution_plan,
            policy=policy,
            plugin_manifests=plugin_manifests,
            tool_contracts=tool_contracts,
            work_role="primary",
            status=_status_for_operation(operation, normalized_text),
            priority=_priority_for_operation(operation, normalized_text, primary=True),
            selection_reason=_selection_reason_for_operation(operation, normalized_text, primary=True),
            evidence=_evidence_for_operation(operation, normalized_text, response_plan),
            blocked_by=list(blocked_by),
        )
    ]
    for detected in _detected_secondary_operations(normalized_text, primary_operation=operation):
        detected_operation = detected["operation"]
        if detected_operation == operation:
            continue
        status = detected.get("status") or _status_for_operation(detected_operation, normalized_text)
        operations.append(
            _operation_candidate(
                operation=detected_operation,
                normalized_text=normalized_text,
                response_plan=response_plan,
                information_gain_plan=information_gain_plan,
                conversation_plan=conversation_plan,
                fulfillment=fulfillment,
                execution_plan=execution_plan,
                policy=policy,
                plugin_manifests=plugin_manifests,
                tool_contracts=tool_contracts,
                work_role=detected.get("work_role", "secondary"),
                status=status,
                priority=detected.get("priority", _priority_for_operation(detected_operation, normalized_text, primary=False)),
                selection_reason=detected.get("selection_reason", _selection_reason_for_operation(detected_operation, normalized_text, primary=False)),
                evidence=detected.get("evidence") or _evidence_for_operation(detected_operation, normalized_text, response_plan),
                blocked_by=[],
            )
        )
    selected_question = _mapping(information_gain_plan.get("selected_question"))
    if selected_question and operation in {"collect_claim_blocker", "continue_conversation_plan", "request_billing_line_item", "request_rejection_detail", "diagnose_connectivity_issue"}:
        operations[0]["dependency"] = {
            "type": "user_information",
            "slot": selected_question.get("slot"),
            "reason": selected_question.get("needed_for") or selected_question.get("purpose"),
        }
        operations[0]["required_information"] = {
            "slot": selected_question.get("slot"),
            "question": selected_question.get("question"),
            "purpose": selected_question.get("purpose"),
        }
    if primary.get("key"):
        operations[0]["primary_user_need"] = primary.get("key")
    return _rank_candidate_work(operations)


def _operation_candidate(
    *,
    operation: str,
    normalized_text: str,
    response_plan: Mapping[str, Any],
    information_gain_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    policy: Mapping[str, Any],
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
    work_role: str,
    status: str,
    priority: int | float,
    selection_reason: str,
    evidence: Mapping[str, Any],
    blocked_by: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    category = _category_for_operation(operation)
    outcome = _outcome_for_operation(
        operation=operation,
        category=category,
        normalized_text=normalized_text,
        information_gain_plan=information_gain_plan,
        fulfillment=fulfillment,
        execution_plan=execution_plan,
        policy=policy,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
    )
    blockers = list(blocked_by) or _blocked_by(
        operation=operation,
        outcome=outcome,
        normalized_text=normalized_text,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
        policy=policy,
    )
    if blockers and status == "pending":
        status = "blocked"
    return {
        "operation": operation,
        "category": category,
        "expected_outcome": outcome,
        "priority": int(priority),
        "status": status,
        "work_role": work_role,
        "evidence": dict(evidence),
        "confidence": _candidate_confidence(operation, normalized_text, work_role=work_role, evidence=evidence),
        "dependency": {},
        "selection_reason": selection_reason,
        "blocked": bool(blockers),
        "blocked_by": [dict(item) for item in blockers],
        "discard_reason": _discard_reason_for_operation(operation, normalized_text, status),
        "suspension_reason": _suspension_reason_for_operation(operation, normalized_text, status),
    }


def _detected_secondary_operations(normalized_text: str, *, primary_operation: str) -> list[dict[str, Any]]:
    detected: list[dict[str, Any]] = []

    def add(
        operation: str,
        *,
        markers: Sequence[str],
        work_role: str = "secondary",
        status: str = "pending",
        priority: int | None = None,
        reason: str | None = None,
    ) -> None:
        matched = [marker for marker in markers if normalize_text(marker) in normalized_text]
        if not matched:
            return
        detected.append(
            {
                "operation": operation,
                "work_role": work_role,
                "status": status,
                "priority": priority or _priority_for_operation(operation, normalized_text, primary=False),
                "selection_reason": reason or "explicit_secondary_user_need",
                "evidence": {
                    "matched_markers": matched,
                    "source": "user_message",
                },
            }
        )

    add("block_real_status_lookup", markers=("consulta mi expediente", "consultar expediente", "estado real", "ver mi expediente", "revisar mi expediente", "revise mi expediente"), work_role="secondary", status="blocked", priority=88, reason="blocked_real_system_request")
    add("block_document_upload", markers=("te mando los documentos", "subir documentos", "cargar documentos por aca", "upload"), work_role="secondary", status="blocked", priority=86, reason="blocked_upload_request")
    add("prevent_unsafe_technical_action", markers=("abrir el modem", "abrir modem", "desarmar el modem"), work_role="secondary", status="pending", priority=96, reason="unsafe_user_requested_action")
    add("provide_repair_risk_guidance", markers=("puedo usar el auto", "arreglar el auto", "reparar el auto", "tocarlo antes", "tocar el auto", "mandarlo a reparar", "auto para trabajar", "mandar el auto al taller", "mandar auto al taller", "auto al taller"), priority=94, reason="repair_may_affect_claim")
    add("prepare_claim_follow_up", markers=("denuncia", "siniestro", "tramite", "nadie me llamo", "nadie me contacto", "nadie me escribio", "novedades", "seguimiento", "sigue en tramite", "app", "respondan", "autorizacion"), priority=78, reason="claim_follow_up_signal")
    add("prepare_documentation_review", markers=("fotos", "foto", "documentacion", "documentos", "presupuesto", "cedula", "captura"), priority=68, reason="documentation_signal")
    add("explain_documentation_requirements", markers=("que documentos", "que documentacion", "documentos me faltan", "documentacion necesito"), priority=66, reason="documentation_question")
    add("prepare_billing_review", markers=("factura", "importe", "monto", "vino mal", "cobraron", "cobro", "vence manana", "vencimiento", "150000", "11000"), priority=72, reason="billing_issue_signal")
    add("request_billing_line_item", markers=("por que me cobraron", "porque me cobraron", "que me cobraron"), priority=73, reason="billing_specific_charge_unknown")
    add("diagnose_connectivity_issue", markers=("no tengo internet", "sin internet", "no funciona el servicio", "no funciona internet", "modem"), priority=74, reason="technical_issue_signal")
    add("prepare_outage_follow_up", markers=("vecinos", "zona", "barrio"), priority=76, reason="possible_area_outage")
    add("prepare_technical_visit", markers=("reinicie todo", "sigue igual", "venga un tecnico", "visita tecnica", "tecnico manana"), priority=80, reason="technical_visit_signal")
    add("prepare_handoff", markers=("persona", "supervisor", "representante", "hablar con alguien", "que me llamen", "me llamen"), work_role="secondary", priority=82, reason="human_owner_requested")
    add("explain_domain_concept", markers=("cleas", "franquicia", "cobertura", "poliza", "cubre", "cristal", "cristales", "cuanto tarda", "tarda normalmente", "cuanto demora"), priority=64, reason="informational_side_need")
    add("prepare_case_summary", markers=("resumime", "resumen"), priority=70, reason="recap_requested")
    add("repair_service_interaction", markers=("ya te lo dije", "nunca dije", "no me estas ayudando", "me confundiste"), priority=90, reason="conversation_repair_needed")
    add("close_case_no_action", markers=("gracias", "quedo claro", "listo"), work_role="completed", status="completed", priority=60, reason="user_closed_work")

    if _has_any(normalized_text, ("dejemos la factura", "no importa la factura", "olvidate de la factura", "factura la vemos despues", "la factura la vemos despues")):
        detected.append(
            {
                "operation": "prepare_billing_review",
                "work_role": "suspended",
                "status": "suspended",
                "priority": 40,
                "selection_reason": "user_suspended_billing_work",
                "evidence": {"matched_markers": ["dejemos la factura"], "source": "user_message"},
            }
        )
    if _has_any(normalized_text, ("dejemos internet", "olvidate de internet")):
        detected.append(
            {
                "operation": "diagnose_connectivity_issue",
                "work_role": "suspended",
                "status": "suspended",
                "priority": 40,
                "selection_reason": "user_suspended_technical_work",
                "evidence": {"matched_markers": ["dejemos internet"], "source": "user_message"},
            }
        )
    if _has_any(normalized_text, ("volvamos a la denuncia", "sobre la denuncia", "retomemos la denuncia")):
        detected.append(
            {
                "operation": "collect_claim_blocker",
                "work_role": "recovered",
                "status": "pending",
                "priority": 84,
                "selection_reason": "user_recovered_claim_work",
                "evidence": {"matched_markers": ["volvamos a la denuncia"], "source": "user_message"},
            }
        )

    unique: dict[str, dict[str, Any]] = {}
    for item in detected:
        operation = str(item["operation"])
        existing = unique.get(operation)
        item_status = str(item.get("status") or "")
        existing_status = str((existing or {}).get("status") or "")
        if existing is None:
            unique[operation] = item
        elif item_status in {"suspended", "recovered", "discarded", "completed"} and existing_status not in {"suspended", "recovered", "discarded", "completed"}:
            unique[operation] = item
        elif int(item.get("priority") or 0) > int(existing.get("priority") or 0):
            unique[operation] = item
    return list(unique.values())


def _rank_candidate_work(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        operation = str(item.get("operation") or "")
        if not operation:
            continue
        mapped = dict(item)
        existing = unique.get(operation)
        if existing is None:
            unique[operation] = mapped
            continue
        if _candidate_sort_key(mapped) < _candidate_sort_key(existing):
            unique[operation] = mapped
    ranked = sorted(unique.values(), key=_candidate_sort_key)
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
        if index == 1:
            item["work_role"] = "primary"
        elif item.get("work_role") == "primary":
            item["work_role"] = "secondary"
    return ranked


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[int, int, str]:
    role_rank = {
        "primary": 0,
        "recovered": 1,
        "secondary": 2,
        "suspended": 3,
        "discarded": 4,
        "completed": 5,
    }.get(str(candidate.get("work_role") or ""), 6)
    return (role_rank, -int(candidate.get("priority") or 0), str(candidate.get("operation") or ""))


def _priority_for_operation(operation: str, normalized_text: str, *, primary: bool) -> int:
    if primary:
        return 100
    if operation in {"provide_repair_risk_guidance", "prevent_unsafe_technical_action"}:
        return 94
    if operation in {"block_real_status_lookup", "block_document_upload"}:
        return 88
    if operation == "prepare_handoff":
        return 82
    if operation == "prepare_technical_visit":
        return 80
    if operation == "prepare_claim_follow_up":
        return 78
    if operation == "diagnose_connectivity_issue":
        return 74
    if operation == "prepare_billing_review":
        return 72
    if operation == "prepare_documentation_review":
        return 68
    if operation.startswith("explain"):
        return 64
    return 60


def _status_for_operation(operation: str, normalized_text: str) -> str:
    if operation in {"block_real_status_lookup", "block_document_upload"}:
        return "blocked"
    if operation == "close_case_no_action":
        return "completed"
    if operation == "prepare_billing_review" and _has_any(normalized_text, ("dejemos la factura", "no importa la factura", "olvidate de la factura", "factura la vemos despues", "la factura la vemos despues")):
        return "suspended"
    if operation == "diagnose_connectivity_issue" and _has_any(normalized_text, ("dejemos internet", "olvidate de internet")):
        return "suspended"
    if _has_any(normalized_text, ("ya quedo", "ya esta resuelto", "ya lo resolvi")):
        return "completed"
    return "pending"


def _selection_reason_for_operation(operation: str, normalized_text: str, *, primary: bool) -> str:
    if primary:
        return "selected_as_dominant_work_from_existing_cognitive_state"
    if operation in {"provide_repair_risk_guidance", "prevent_unsafe_technical_action"}:
        return "protective_work_has_high_operational_value"
    if operation in {"block_real_status_lookup", "block_document_upload"}:
        return "capability_or_tool_limit_must_remain_visible"
    if operation == "prepare_handoff":
        return "user_requested_human_or_coordinated_owner"
    return "additional_user_need_detected_in_same_turn"


def _evidence_for_operation(
    operation: str,
    normalized_text: str,
    response_plan: Mapping[str, Any],
) -> dict[str, Any]:
    markers_by_operation = {
        "prepare_billing_review": ("factura", "importe", "monto", "cobraron", "vence", "vino mal"),
        "diagnose_connectivity_issue": ("internet", "modem", "no funciona"),
        "prepare_technical_visit": ("tecnico", "reinicie", "sigue igual"),
        "provide_repair_risk_guidance": ("arreglar", "reparar", "tocarlo", "auto para trabajar"),
        "prepare_claim_follow_up": ("denuncia", "siniestro", "nadie", "novedades", "tramite", "respondan", "autorizacion"),
        "prepare_documentation_review": ("fotos", "documentacion", "documentos", "presupuesto", "cedula"),
        "prepare_handoff": ("persona", "supervisor", "representante", "me llamen"),
        "block_real_status_lookup": ("consulta mi expediente", "estado real"),
        "block_document_upload": ("mando los documentos", "subir documentos"),
        "explain_domain_concept": ("cleas", "franquicia", "cobertura", "poliza", "cubre", "cuanto tarda"),
    }
    matched = [
        marker
        for marker in markers_by_operation.get(operation, ())
        if normalize_text(marker) in normalized_text
    ]
    primary = _mapping(response_plan.get("primary_user_need"))
    evidence: dict[str, Any] = {
        "matched_markers": matched,
        "source": "user_message" if matched else "cognitive_state",
    }
    if primary.get("key"):
        evidence["primary_user_need"] = primary.get("key")
    return evidence


def _candidate_confidence(
    operation: str,
    normalized_text: str,
    *,
    work_role: str,
    evidence: Mapping[str, Any],
) -> float:
    if work_role == "primary":
        return 0.95
    score = 0.55
    if evidence.get("matched_markers"):
        score += 0.25
    if work_role in {"suspended", "recovered", "completed"}:
        score += 0.1
    if operation in {"provide_repair_risk_guidance", "block_real_status_lookup", "block_document_upload"}:
        score += 0.05
    return min(round(score, 2), 0.9)


def _discard_reason_for_operation(operation: str, normalized_text: str, status: str) -> str:
    if status != "discarded":
        return ""
    return "user_indicated_work_is_no_longer_needed"


def _suspension_reason_for_operation(operation: str, normalized_text: str, status: str) -> str:
    if status != "suspended":
        return ""
    return "user_explicitly_deferred_this_work"


def _candidate_summary(candidate_work: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_count": len(candidate_work),
        "primary": [
            item.get("operation")
            for item in candidate_work
            if item.get("work_role") == "primary"
        ],
        "secondary": [
            item.get("operation")
            for item in candidate_work
            if item.get("work_role") == "secondary"
        ],
        "suspended": [
            item.get("operation")
            for item in candidate_work
            if item.get("status") == "suspended"
        ],
        "blocked": [
            item.get("operation")
            for item in candidate_work
            if item.get("status") == "blocked"
        ],
        "completed": [
            item.get("operation")
            for item in candidate_work
            if item.get("status") == "completed"
        ],
    }


def _case_state_projection(
    *,
    normalized_text: str,
    final_conversation_state: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    runtime_outcomes: Sequence[Any],
    candidate_work: Sequence[Mapping[str, Any]],
    required_information: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a non-authoritative operational case view from existing state."""

    mission = _mapping(final_conversation_state.get("active_mission"))
    confirmed_facts = _mapping(final_conversation_state.get("confirmed_facts"))
    plan_steps = list(_mapping(conversation_plan.get("active_plan")).get("steps") or [])
    pending_steps = list(conversation_plan.get("pending_steps") or [])
    completed_steps = list(conversation_plan.get("completed_steps") or [])
    fulfilled_steps = list(fulfillment.get("fulfilled_steps") or [])
    candidate_operations = [str(_mapping(candidate).get("operation") or "") for candidate in candidate_work]
    claim_loaded = _claim_report_loaded(normalized_text, confirmed_facts, plan_steps, candidate_work)
    follow_up_needed = _claim_follow_up_needed(normalized_text, candidate_work)
    documentation_state = _documentation_case_state(normalized_text, candidate_work)
    repair_state = _repair_case_state(normalized_text, candidate_work)
    technical_state = _technical_case_state(normalized_text, candidate_work)
    billing_state = _billing_case_state(normalized_text, candidate_work)
    stage = _case_stage(
        mission=mission,
        execution_plan=execution_plan,
        claim_loaded=claim_loaded,
        follow_up_needed=follow_up_needed,
        documentation_state=documentation_state,
        repair_state=repair_state,
        technical_state=technical_state,
        billing_state=billing_state,
        candidate_operations=candidate_operations,
    )
    pending_actions = _case_pending_actions(
        candidate_work=candidate_work,
        claim_loaded=claim_loaded,
        follow_up_needed=follow_up_needed,
        documentation_state=documentation_state,
        repair_state=repair_state,
        technical_state=technical_state,
        billing_state=billing_state,
    )
    completed_actions = _case_completed_actions(
        normalized_text=normalized_text,
        candidate_work=candidate_work,
        claim_loaded=claim_loaded,
        documentation_state=documentation_state,
    )
    blockers = _case_blockers(candidate_work)
    return {
        "component": "case_state_projection_shadow",
        "mode": "shadow",
        "derived": True,
        "persistent": False,
        "mutates_state": False,
        "source_of_truth": "ConversationState",
        "reconstructable_each_turn": True,
        "case_stage": stage,
        "documentation": documentation_state,
        "repair": repair_state,
        "technical_service": technical_state,
        "billing": billing_state,
        "claim": {
            "loaded": claim_loaded,
            "follow_up_needed": follow_up_needed,
            "mission_type": mission.get("type"),
            "mission_status": mission.get("status"),
            "mission_lifecycle_status": mission.get("lifecycle_status"),
        },
        "current_owner": _case_current_owner(
            blockers=blockers,
            pending_actions=pending_actions,
            required_information=required_information,
            stage=stage,
        ),
        "blockers": blockers,
        "dependencies": [dict(item) for item in required_information],
        "pending_actions": pending_actions,
        "completed_actions": completed_actions,
        "available_evidence": _case_available_evidence(
            normalized_text=normalized_text,
            confirmed_facts=confirmed_facts,
            candidate_work=candidate_work,
        ),
        "expected_next_change": _case_expected_next_change(
            stage=stage,
            pending_actions=pending_actions,
            blockers=blockers,
        ),
        "derived_from": {
            "conversation_state": bool(final_conversation_state),
            "confirmed_facts": bool(confirmed_facts),
            "conversation_plan": bool(conversation_plan),
            "conversation_fulfillment": bool(fulfillment),
            "execution_plan": bool(execution_plan),
            "runtime_outcomes": len(runtime_outcomes),
            "candidate_work": bool(candidate_work),
        },
        "projection_notes": _case_projection_notes(
            claim_loaded=claim_loaded,
            follow_up_needed=follow_up_needed,
            documentation_state=documentation_state,
            pending_steps=pending_steps,
            completed_steps=completed_steps,
            fulfilled_steps=fulfilled_steps,
        ),
    }


def _case_state_projected_ranking(
    *,
    candidate_work: Sequence[Mapping[str, Any]],
    case_state_projection: Mapping[str, Any],
) -> dict[str, Any]:
    projected = []
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        score, reasons = _case_state_candidate_score(mapped, case_state_projection)
        projected.append(
            {
                "operation": mapped.get("operation"),
                "original_rank": mapped.get("rank"),
                "original_priority": mapped.get("priority"),
                "projected_score": score,
                "status": mapped.get("status"),
                "work_role": mapped.get("work_role"),
                "reasons": reasons,
            }
        )
    ranked = sorted(
        projected,
        key=lambda item: (-int(item.get("projected_score") or 0), int(item.get("original_rank") or 999)),
    )
    for index, item in enumerate(ranked, start=1):
        item["projected_rank"] = index
    original_order = [str(_mapping(candidate).get("operation") or "") for candidate in candidate_work]
    projected_order = [str(item.get("operation") or "") for item in ranked]
    return {
        "mode": "shadow_projection",
        "uses_case_state_projection": True,
        "changes_candidate_work": False,
        "changed_order": projected_order != original_order,
        "original_order": original_order,
        "projected_order": projected_order,
        "ranked_candidates": ranked,
    }


def _case_state_candidate_score(
    candidate: Mapping[str, Any],
    case_state_projection: Mapping[str, Any],
) -> tuple[int, list[str]]:
    operation = str(candidate.get("operation") or "")
    status = str(candidate.get("status") or "")
    score = int(candidate.get("priority") or 0)
    reasons = ["base_candidate_priority"]
    claim = _mapping(case_state_projection.get("claim"))
    documentation = _mapping(case_state_projection.get("documentation"))
    repair = _mapping(case_state_projection.get("repair"))
    technical = _mapping(case_state_projection.get("technical_service"))
    billing = _mapping(case_state_projection.get("billing"))
    stage = str(case_state_projection.get("case_stage") or "")
    if stage != "documentation_pending_after_claim_loaded":
        return score, reasons + ["case_state_projection_no_ranking_adjustment"]

    if status == "suspended":
        score -= 80
        reasons.append("suspended_work_demoted")
    if status == "completed":
        score -= 45
        reasons.append("completed_work_demoted")
    if operation == "prepare_documentation_review" and documentation.get("state") in {"unknown_or_pending", "pending", "blocked_upload"}:
        score += 90
        reasons.append("documentation_is_active_case_uncertainty")
    if operation == "prepare_claim_follow_up" and claim.get("loaded") and not claim.get("follow_up_needed"):
        score -= 65
        reasons.append("claim_loaded_without_follow_up_signal")
    if operation == "prepare_claim_follow_up" and claim.get("follow_up_needed"):
        score += 45
        reasons.append("claim_follow_up_needed")
    if operation == "provide_repair_risk_guidance" and repair.get("state") == "risk_active":
        score += 45
        reasons.append("repair_risk_active")
    if operation == "diagnose_connectivity_issue" and technical.get("state") in {"issue_open", "service_down"}:
        score += 35
        reasons.append("technical_issue_open")
    if operation == "prepare_billing_review" and billing.get("state") == "issue_open":
        score += 35
        reasons.append("billing_issue_open")
    if operation == "close_case_no_action" and case_state_projection.get("pending_actions"):
        score -= 45
        reasons.append("case_has_pending_actions")
    if stage == "documentation_pending_after_claim_loaded" and operation == "prepare_documentation_review":
        score += 25
        reasons.append("case_stage_prioritizes_documentation")
    return score, reasons


def _claim_report_loaded(
    normalized_text: str,
    confirmed_facts: Mapping[str, Any],
    plan_steps: Sequence[Any],
    candidate_work: Sequence[Mapping[str, Any]],
) -> bool:
    if _has_any(
        normalized_text,
        (
            "denuncia ya quedo cargada",
            "denuncia ya esta cargada",
            "la denuncia ya quedo cargada",
            "la denuncia ya esta cargada",
            "ya cargue la denuncia",
            "denuncia cargada",
            "cargue la denuncia",
        ),
    ):
        return True
    if _has_any(normalize_text(str(confirmed_facts)), ("claim_report_loaded", "denuncia cargada")):
        return True
    for step in plan_steps:
        mapped = _mapping(step)
        if mapped.get("fact") == "claim_report_loaded" and mapped.get("status") in {"completed", "fulfilled"}:
            return True
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        if mapped.get("operation") == "prepare_claim_follow_up" and mapped.get("status") == "completed":
            return True
    return False


def _claim_follow_up_needed(normalized_text: str, candidate_work: Sequence[Mapping[str, Any]]) -> bool:
    if _has_any(
        normalized_text,
        (
            "sigue en tramite",
            "nadie me contacto",
            "nadie me llamo",
            "nadie me escribio",
            "sin novedades",
            "no recibi novedades",
            "hace una semana",
            "seguimiento",
        ),
    ):
        return True
    return any(
        _mapping(candidate).get("operation") == "prepare_claim_follow_up"
        and _mapping(candidate).get("status") not in {"completed", "suspended"}
        and _mapping(_mapping(candidate).get("evidence")).get("matched_markers")
        for candidate in candidate_work
    )


def _documentation_case_state(normalized_text: str, candidate_work: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evidence: list[str] = []
    if _has_any(normalized_text, ("faltan documentos", "documentos me faltan", "falta documentacion", "no se si faltan documentos")):
        evidence.append("documentation_missing_or_unknown_marker")
        state = "unknown_or_pending"
    elif _has_any(normalized_text, ("tengo toda la documentacion", "documentacion completa", "tengo fotos", "tengo presupuesto")):
        evidence.append("documentation_available_marker")
        state = "available"
    elif _has_any(normalized_text, ("fotos", "documentos", "documentacion", "presupuesto", "cedula")):
        evidence.append("documentation_signal")
        state = "unknown_or_pending"
    else:
        state = "not_observed"
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        if mapped.get("operation") == "block_document_upload":
            state = "blocked_upload"
            evidence.append("blocked_upload_candidate")
        if mapped.get("operation") == "prepare_documentation_review" and mapped.get("blocked"):
            if state in {"not_observed", "unknown_or_pending"}:
                state = "blocked_upload"
            evidence.append("documentation_candidate_blocked_by_capability")
    return {"state": state, "evidence": _unique_strings(evidence)}


def _repair_case_state(normalized_text: str, candidate_work: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if _has_any(
        normalized_text,
        ("arreglar el auto", "reparar el auto", "tocarlo antes", "mandarlo a reparar", "auto para trabajar", "auto al taller"),
    ) or any(_mapping(candidate).get("operation") == "provide_repair_risk_guidance" for candidate in candidate_work):
        return {"state": "risk_active", "evidence": ["repair_risk_signal"]}
    return {"state": "not_observed", "evidence": []}


def _technical_case_state(normalized_text: str, candidate_work: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if any(_mapping(candidate).get("operation") == "prepare_technical_visit" for candidate in candidate_work):
        return {"state": "visit_needed_or_scheduled", "evidence": ["technical_visit_candidate"]}
    if any(_mapping(candidate).get("operation") == "prepare_outage_follow_up" for candidate in candidate_work):
        return {"state": "possible_area_outage", "evidence": ["outage_candidate"]}
    if _has_any(normalized_text, ("no tengo internet", "sin internet", "no funciona internet", "no funciona el servicio", "modem")):
        return {"state": "issue_open", "evidence": ["technical_issue_marker"]}
    return {"state": "not_observed", "evidence": []}


def _billing_case_state(normalized_text: str, candidate_work: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if any(
        _mapping(candidate).get("operation") == "prepare_billing_review"
        and _mapping(candidate).get("status") == "suspended"
        for candidate in candidate_work
    ):
        return {"state": "suspended", "evidence": ["billing_suspended_candidate"]}
    if _has_any(normalized_text, ("factura", "cobraron", "cobro", "monto", "vencimiento", "vence manana")):
        return {"state": "issue_open", "evidence": ["billing_marker"]}
    return {"state": "not_observed", "evidence": []}


def _case_stage(
    *,
    mission: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    claim_loaded: bool,
    follow_up_needed: bool,
    documentation_state: Mapping[str, Any],
    repair_state: Mapping[str, Any],
    technical_state: Mapping[str, Any],
    billing_state: Mapping[str, Any],
    candidate_operations: Sequence[str],
) -> str:
    if claim_loaded and follow_up_needed:
        return "claim_loaded_follow_up_needed"
    if claim_loaded and documentation_state.get("state") in {"unknown_or_pending", "pending", "blocked_upload"}:
        return "documentation_pending_after_claim_loaded"
    if claim_loaded:
        return "claim_report_loaded"
    if repair_state.get("state") == "risk_active":
        return "repair_authorization_risk"
    if technical_state.get("state") != "not_observed":
        return str(technical_state.get("state"))
    if billing_state.get("state") != "not_observed":
        return str(billing_state.get("state"))
    if str(mission.get("type") or "") == "auto_claim_guidance" or "auto_claim_guidance" in str(execution_plan.get("kernel_program") or ""):
        return "claim_guidance_in_progress"
    if "close_case_no_action" in candidate_operations:
        return "case_closed_or_no_action_required"
    return "unknown"


def _case_pending_actions(
    *,
    candidate_work: Sequence[Mapping[str, Any]],
    claim_loaded: bool,
    follow_up_needed: bool,
    documentation_state: Mapping[str, Any],
    repair_state: Mapping[str, Any],
    technical_state: Mapping[str, Any],
    billing_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if documentation_state.get("state") in {"unknown_or_pending", "pending", "blocked_upload"}:
        actions.append({"operation": "prepare_documentation_review", "reason": "documentation_state_unresolved"})
    if follow_up_needed:
        actions.append({"operation": "prepare_claim_follow_up", "reason": "claim_follow_up_needed"})
    if repair_state.get("state") == "risk_active":
        actions.append({"operation": "provide_repair_risk_guidance", "reason": "repair_risk_active"})
    if technical_state.get("state") in {"issue_open", "possible_area_outage", "visit_needed_or_scheduled"}:
        actions.append({"operation": "diagnose_connectivity_issue", "reason": "technical_state_open"})
    if billing_state.get("state") == "issue_open":
        actions.append({"operation": "prepare_billing_review", "reason": "billing_issue_open"})
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        if mapped.get("status") in {"pending", "blocked"} and mapped.get("operation"):
            actions.append({"operation": mapped.get("operation"), "reason": "candidate_work"})
    if claim_loaded and not follow_up_needed:
        actions = [
            action
            for action in actions
            if action.get("operation") != "prepare_claim_follow_up"
            or action.get("reason") != "candidate_work"
        ]
    return _unique_dicts(actions)


def _case_completed_actions(
    *,
    normalized_text: str,
    candidate_work: Sequence[Mapping[str, Any]],
    claim_loaded: bool,
    documentation_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if claim_loaded:
        actions.append({"operation": "claim_report_loaded", "reason": "case_state_evidence"})
    if documentation_state.get("state") == "available":
        actions.append({"operation": "documentation_available", "reason": "case_state_evidence"})
    if _has_any(normalized_text, ("listo", "quedo claro", "ya quedo")):
        actions.append({"operation": "user_indicated_partial_or_full_completion", "reason": "user_marker"})
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        if mapped.get("status") == "completed" and mapped.get("operation"):
            actions.append({"operation": mapped.get("operation"), "reason": "candidate_completed"})
    return _unique_dicts(actions)


def _case_blockers(candidate_work: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        for blocker in mapped.get("blocked_by") or []:
            blocker_mapped = _mapping(blocker)
            if blocker_mapped:
                blocker_mapped["operation"] = mapped.get("operation")
                blockers.append(blocker_mapped)
    return _unique_dicts(blockers)


def _case_current_owner(
    *,
    blockers: Sequence[Mapping[str, Any]],
    pending_actions: Sequence[Mapping[str, Any]],
    required_information: Sequence[Mapping[str, Any]],
    stage: str,
) -> str:
    if blockers:
        return "external_system_or_capability_owner"
    if required_information:
        return "user"
    if pending_actions:
        return "aca_shadow_representative"
    if stage in {"waiting_for_system", "visit_needed_or_scheduled"}:
        return "provider"
    return "none"


def _case_available_evidence(
    *,
    normalized_text: str,
    confirmed_facts: Mapping[str, Any],
    candidate_work: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    evidence = []
    if normalized_text:
        evidence.append({"source": "last_user_message", "available": True})
    if confirmed_facts:
        evidence.append({"source": "confirmed_facts", "keys": sorted(str(key) for key in confirmed_facts.keys())})
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        markers = _mapping(mapped.get("evidence")).get("matched_markers")
        if markers:
            evidence.append({"source": "candidate_work", "operation": mapped.get("operation"), "markers": list(markers)})
    return _unique_dicts(evidence)


def _case_expected_next_change(
    *,
    stage: str,
    pending_actions: Sequence[Mapping[str, Any]],
    blockers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if blockers:
        return {"type": "capability_or_system_resolution", "stage": stage}
    if pending_actions:
        return {"type": "complete_next_pending_action", "operation": _mapping(pending_actions[0]).get("operation"), "stage": stage}
    return {"type": "none", "stage": stage}


def _case_projection_notes(
    *,
    claim_loaded: bool,
    follow_up_needed: bool,
    documentation_state: Mapping[str, Any],
    pending_steps: Sequence[Any],
    completed_steps: Sequence[Any],
    fulfilled_steps: Sequence[Any],
) -> list[str]:
    notes = []
    if claim_loaded:
        notes.append("claim_report_loaded_derived_from_existing_evidence")
    if follow_up_needed:
        notes.append("claim_follow_up_needed_derived_from_turn_or_candidates")
    if documentation_state.get("state") in {"unknown_or_pending", "blocked_upload"}:
        notes.append("documentation_state_requires_operational_ranking_attention")
    if pending_steps:
        notes.append("conversation_plan_has_pending_steps")
    if completed_steps:
        notes.append("conversation_plan_has_completed_steps")
    if fulfilled_steps:
        notes.append("conversation_fulfillment_has_fulfilled_steps")
    return notes


def _available_tools(
    *,
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tools = [
        {
            "name": name,
            "contract": deepcopy(contract),
            "source": "tool_engine",
        }
        for name, contract in sorted(tool_contracts.items())
    ]
    for manifest in plugin_manifests:
        plugin_id = _mapping(manifest.get("plugin")).get("id") or manifest.get("id")
        for capability in manifest.get("handles") or []:
            tools.append(
                {
                    "name": str(capability),
                    "plugin_id": plugin_id,
                    "source": "plugin_manifest",
                    "blocked": False,
                }
            )
        for capability in manifest.get("blocked_capabilities") or []:
            tools.append(
                {
                    "name": str(capability),
                    "plugin_id": plugin_id,
                    "source": "plugin_manifest",
                    "blocked": True,
                }
            )
    return tools


def _confidence(
    *,
    operation: str,
    response_plan: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    policy: Mapping[str, Any],
    normalized_text: str,
) -> float:
    if operation == "no_operational_work_identified":
        return 0.2
    score = 0.45
    if _mapping(response_plan.get("primary_user_need")).get("key"):
        score += 0.2
    if execution_plan.get("flow"):
        score += 0.15
    if policy.get("decision"):
        score += 0.1
    if normalized_text:
        score += 0.1
    return min(round(score, 2), 0.95)


def _operational_value(outcome: str, *, impossible: bool) -> int:
    values = {
        "completed": 3,
        "prepared": 2,
        "delegated": 2,
        "explained": 1,
        "blocked": 1,
        "unsafe_operation": 1,
        "waiting_for_user": 1,
        "waiting_for_system": 1,
        "no_action_required": 0,
    }
    return max(values.get(outcome, 0) - (2 if impossible else 0), 0)


def _role_from_state(
    conversation_state: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    normalized_text: str,
) -> str:
    mission = _mapping(conversation_state.get("active_mission"))
    if mission.get("type") == "auto_claim_guidance" or _has_any(normalized_text, ("denuncia", "siniestro", "choque")):
        return "first_line_insurance_representative"
    if _has_any(normalized_text, ("internet", "modem", "tecnico")):
        return "first_line_technical_support_representative"
    if _has_any(normalized_text, ("factura", "cobraron", "monto")):
        return "first_line_billing_representative"
    if execution_plan.get("flow"):
        return "first_line_service_representative"
    return "general_support_representative"


def _responsibility_for_operation(operation: str) -> str:
    if operation.startswith("prepare_claim") or operation in {"collect_claim_blocker", "start_claim_guidance", "provide_repair_risk_guidance"}:
        return "advance_claim_or_sinister_case_safely"
    if "billing" in operation:
        return "prepare_billing_issue_review"
    if "technical" in operation or "connectivity" in operation or "outage" in operation:
        return "restore_or_coordinate_service_recovery"
    if "document" in operation:
        return "prepare_or_explain_documentation_work"
    if "handoff" in operation:
        return "delegate_with_context_when_needed"
    if "explain" in operation:
        return "reduce_user_uncertainty"
    return "preserve_case_progress"


def _conversation_plan_coherence(operation: str, plan: Mapping[str, Any]) -> dict[str, Any]:
    current_step = _mapping(_mapping(plan.get("active_plan")).get("current_step"))
    pending_steps = [_mapping(step).get("id") for step in plan.get("pending_steps") or []]
    coherent = True
    reason = "no_plan_available"
    if current_step:
        step_id = str(current_step.get("id") or "")
        reason = f"current_step:{step_id}"
        if operation == "collect_claim_blocker":
            coherent = current_step.get("type") in {"slot", "fact"}
        elif operation.startswith("prepare_claim"):
            coherent = True
    return {
        "coherent": coherent,
        "reason": reason,
        "current_step": current_step.get("id"),
        "pending_steps": pending_steps,
    }


def _execution_plan_coherence(operation: str, execution_plan: Mapping[str, Any]) -> dict[str, Any]:
    flow = str(execution_plan.get("flow") or "")
    program = str(execution_plan.get("kernel_program") or "")
    if not flow:
        return {"coherent": False, "reason": "execution_plan_missing"}
    if operation == "explain_domain_concept":
        coherent = flow in {"knowledge_lookup", "fallback", "static_response", "guided_process"}
    elif operation == "prepare_handoff":
        coherent = flow in {"human_handoff", "safe_escalation", "guided_process"}
    elif "claim" in operation or operation == "provide_repair_risk_guidance":
        coherent = program == "auto_claim_guidance" or flow in {"guided_process", "knowledge_lookup"}
    else:
        coherent = True
    return {"coherent": coherent, "flow": flow, "kernel_program": program}


def _policy_coherence(policy: Mapping[str, Any]) -> dict[str, Any]:
    decision = str(policy.get("decision") or "")
    return {
        "coherent": decision not in {"DENY"} if decision else True,
        "decision": decision,
        "reason": policy.get("reason"),
    }


def _capability_for_operation(operation: str) -> str:
    return {
        "prepare_claim_follow_up": "insurance.claim_status.lookup",
        "block_real_status_lookup": "insurance.claim_status.lookup",
        "prepare_documentation_review": "insurance.document.upload",
        "block_document_upload": "insurance.document.upload",
        "prepare_handoff": "insurance.handoff.prepare",
        "provide_repair_risk_guidance": "insurance.claims",
        "collect_claim_blocker": "insurance.claims",
        "start_claim_guidance": "insurance.claims",
        "explain_documentation_requirements": "insurance.claims",
        "explain_domain_concept": "insurance.claims",
    }.get(operation, "")


def _public_action_for_capability(
    plugin_manifests: Sequence[Mapping[str, Any]],
    capability: str,
) -> dict[str, Any]:
    for manifest in plugin_manifests:
        for action in manifest.get("public_actions") or []:
            mapped = _mapping(action)
            if mapped.get("capability") == capability:
                return mapped
    return {}


def _capability_blocked(plugin_manifests: Sequence[Mapping[str, Any]], capability: str) -> bool:
    return any(capability in set(manifest.get("blocked_capabilities") or []) for manifest in plugin_manifests)


def _suggests_impossible_work(
    *,
    operation: str,
    outcome: str,
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
) -> bool:
    capability = _capability_for_operation(operation)
    if not capability:
        return False
    if outcome in {"blocked", "prepared", "delegated", "explained", "unsafe_operation", "waiting_for_user", "waiting_for_system", "no_action_required"}:
        return False
    return _capability_blocked(plugin_manifests, capability) and not tool_contracts


def _operation_matches(actual: str, expected: str) -> bool:
    if not expected:
        return False
    if actual == expected:
        return True
    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)
    if actual_norm == expected_norm:
        return True
    aliases = {
        "explain concept": {"explain_domain_concept"},
        "explain general timing and variables": {"explain_domain_concept", "prepare_claim_follow_up"},
        "protective guidance": {"provide_repair_risk_guidance"},
        "prepare follow-up review": {"prepare_claim_follow_up"},
        "prepare status follow-up": {"prepare_claim_follow_up"},
        "prepare billing review": {"prepare_billing_review"},
        "prepare discrepancy review": {"prepare_billing_review"},
        "ask for bill line or explain need": {"request_billing_line_item", "prepare_billing_review"},
        "prepare review using evidence": {"prepare_billing_review", "prepare_documentation_review"},
        "diagnose or prepare service check": {"diagnose_connectivity_issue", "prepare_outage_follow_up", "prepare_technical_visit"},
        "explain likely area issue / prepare outage follow-up": {"prepare_outage_follow_up"},
        "prepare support priority or workaround": {"diagnose_connectivity_issue", "prepare_outage_follow_up"},
        "prepare technical visit request": {"prepare_technical_visit"},
        "start claim guidance": {"start_claim_guidance", "collect_claim_blocker"},
        "advance mission to role": {"collect_claim_blocker"},
        "continue claim guidance": {"collect_claim_blocker", "continue_conversation_plan"},
        "ask next operation-changing item": {"collect_claim_blocker"},
        "advance to documentation/next step": {"collect_claim_blocker", "prepare_documentation_review"},
        "explain required docs": {"explain_documentation_requirements"},
        "prepare documentation checklist/association": {"prepare_documentation_review"},
        "explain possible reasons and prepare check": {"explain_documentation_requirements", "prepare_documentation_review"},
        "ask rejection-changing info": {"request_rejection_detail"},
        "prepare callback request or handoff": {"prepare_handoff"},
        "prepare visit request if diagnostics satisfied": {"prepare_technical_visit"},
        "prepare review/escalation": {"prepare_claim_follow_up", "prepare_handoff"},
        "prepare handoff package": {"prepare_handoff"},
        "prepare escalated handoff": {"prepare_handoff"},
        "explain limit and prepare specialized handoff": {"prepare_handoff", "block_real_status_lookup"},
        "repair using known state": {"repair_service_interaction"},
        "correct case focus": {"repair_service_interaction", "prepare_claim_follow_up"},
        "offer concrete operation options": {"repair_service_interaction"},
        "protective guidance + prepare doc check": {"provide_repair_risk_guidance"},
        "select urgent or ask priority": {"continue_conversation_plan", "diagnose_connectivity_issue", "prepare_billing_review"},
        "protective repair guidance + timing explanation": {"provide_repair_risk_guidance", "prepare_claim_follow_up"},
        "answer timing and preserve plan": {"explain_domain_concept", "prepare_claim_follow_up"},
        "start technical diagnosis": {"diagnose_connectivity_issue"},
        "resume prior case": {"collect_claim_blocker", "prepare_claim_follow_up", "continue_conversation_plan"},
        "resolve pending slot": {"collect_claim_blocker", "continue_conversation_plan"},
        "reask with context": {"collect_claim_blocker", "continue_conversation_plan"},
        "ask what service/case": {"continue_conversation_plan"},
        "de-escalate + prepare review": {"prepare_billing_review", "repair_service_interaction"},
        "identify actual service problem": {"diagnose_connectivity_issue", "continue_conversation_plan"},
        "prepare follow-up/escalation": {"prepare_claim_follow_up", "prepare_handoff"},
        "simplify current operation/status": {"explain_current_step_simpler"},
        "produce case/work summary": {"prepare_case_summary"},
        "block real lookup, offer prepared follow-up": {"block_real_status_lookup"},
        "block upload, explain channel or prepare checklist": {"block_document_upload"},
        "prevent unsafe operation": {"prevent_unsafe_technical_action"},
        "close/no further action": {"close_case_no_action"},
        "mark waiting_for_system": {"prepare_technical_visit"},
    }
    if actual_norm in normalize_text(expected).replace(" ", "_"):
        return True
    return actual in aliases.get(expected_norm, set())


def _has_any(normalized_text: str, markers: Sequence[str]) -> bool:
    return any(normalize_text(marker) in normalized_text for marker in markers)


def _unique_dicts(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        compact = {key: value for key, value in dict(item).items() if value not in (None, "", [], {})}
        signature = tuple(sorted((str(key), str(value)) for key, value in compact.items()))
        if signature not in seen:
            seen.add(signature)
            unique.append(compact)
    return unique


def _unique_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        item = str(value or "")
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
