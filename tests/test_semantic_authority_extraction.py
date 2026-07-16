from types import SimpleNamespace

from aca_kernel.core.events import Event
from aca_os.semantic_authority import SemanticAuthority
from aca_os.semantic_understanding_evaluation import run_semantic_understanding_evaluation


def _context(**overrides):
    values = {
        "conversation_id": "sa-2.6-generalization",
        "turn_count": 0,
        "confirmed_facts": {},
        "topic_stack": [],
        "pending_questions": [],
        "relevant_context": {},
        "active_mission": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _interpret(message: str, *, context=None):
    return SemanticAuthority().interpret(
        Event(type="user_message", payload=message),
        conversation_state=context or _context(),
        turn_number=1,
    ).to_dict()


def test_syntactic_entity_roles_generalize_beyond_benchmark_values():
    result = _interpret(
        "Me llamo Abril. Vivo en Mar del Plata. Tengo una mascota llamada Fenix. "
        "Trabajo en Horizonte Cooperativa y uso el producto Cobertura Empresa."
    )
    entities = {(item["type"], item["value"]) for item in result["entities"]}

    assert ("person", "Abril") in entities
    assert ("place", "Mar del Plata") in entities
    assert ("animal", "Fenix") in entities
    assert ("organization", "Horizonte Cooperativa") in entities
    assert ("product", "Cobertura Empresa") in entities


def test_negation_scope_maps_general_lexical_cues_to_false_facts():
    result = _interpret(
        "No hubo ninguna persona lesionada. Nunca me contactaron y todavia no "
        "resolvieron el caso. No quiero presentar la denuncia. El servicio de "
        "video dejo de funcionar."
    )
    facts = {
        (item["predicate"], item["value"])
        for item in result["assertions"]
        if item["predicate"] not in {"user_statement", "user_question"}
    }

    assert ("injuries", False) in facts
    assert ("contact_received", False) in facts
    assert ("case_resolved", False) in facts
    assert ("claim_submission_intent", False) in facts
    assert ("service_available", False) in facts


def test_temporal_normalization_covers_relative_since_and_sequence_expressions():
    result = _interpret(
        "Ayer abri el caso. Desde ayer sigue igual y manana vuelvo a llamar. "
        "Primero reviso el correo y despues envio el comprobante."
    )
    temporal = {
        item["value"]
        for item in result["entities"]
        if item["type"] == "temporal_expression"
    }

    assert {"Ayer", "Desde ayer", "manana", "Primero", "despues"} <= temporal


def test_correction_retraction_and_ambiguity_are_independent_operations():
    result = _interpret(
        "Quise decir otra cosa. Mejor dejemos ese tema. No puedo precisar el dato."
    )

    assert {item["operation"] for item in result["corrections"]} == {
        "replace_prior_assertion",
        "retract",
    }
    assert result["uncertainty"][0]["type"] == "user_uncertainty"


def test_coreference_uses_read_only_context_and_records_grounding():
    result = _interpret(
        "Ella necesita que la llamen.",
        context=_context(relevant_context={"contact": {"type": "person", "value": "Renata"}}),
    )
    reference = result["grounding"]["resolved_coreferences"][0]

    assert reference["mention"] == "ella"
    assert reference["target_type"] == "person"
    assert reference["target_value"] == "Renata"
    assert result["grounding"]["grounding_mode"] == "read_only_shadow"


def test_extracted_semantics_include_auditable_provenance():
    result = _interpret(
        "Me llamo Abril. No funciona el servicio de video desde ayer.",
    )
    semantic_items = list(result["entities"]) + [
        item
        for item in result["assertions"]
        if item["predicate"] not in {"user_statement", "user_question"}
    ]

    assert semantic_items
    for item in semantic_items:
        assert item["confidence"] > 0
        assert item["rule"]
        assert item["evidence"]["segment_id"]
        assert item["evidence"]["text"]
        assert item["evidence"]["span"]["end"] > item["evidence"]["span"]["start"]


def test_frozen_sa_2_5_benchmark_improves_without_authority_promotion():
    result = run_semantic_understanding_evaluation()
    metrics = result["summary"]["metrics"]

    assert result["benchmark"]["benchmark_hash"] == (
        "79c644695143252969f4dde4e4e94b6dbabe6c7813c6733ddaed5340057ac5bd"
    )
    assert result["engine"]["mode"] == "shadow"
    assert result["engine"]["decision_influence"] is False
    assert result["engine"]["state_mutation"] is False
    assert result["summary"]["semantic_understanding_score"] > 0.90
    assert metrics["entity_recall"] > 0.90
    assert metrics["fact_recall"] > 0.90
    assert metrics["negation_accuracy"] > 0.95
    assert metrics["correction_accuracy"] > 0.95
    assert metrics["retraction_accuracy"] > 0.95
    assert metrics["coreference_accuracy"] > 0.85
    assert metrics["temporal_accuracy"] > 0.85
