from copy import deepcopy
from pathlib import Path

from aca_os.authority_dependency_graph import build_authority_dependency_graph
from aca_os.operational_work_mapper import map_operational_work
from aca_os.semantic_firewall_plan import build_semantic_firewall_refactoring_plan


ROOT = Path(__file__).resolve().parents[1]


def _semantic_projection() -> dict:
    return {
        "contract": "semantic_projection.v1",
        "intent_projection": {
            "selected": {
                "intent": "restore_connectivity",
                "confidence": 0.91,
            },
            "candidates": [
                {"intent": "restore_connectivity", "confidence": 0.91},
                {"intent": "review_billing", "confidence": 0.82},
            ],
        },
        "topic_projection": {
            "topics": [
                {"type": "connectivity"},
                {"type": "billing"},
            ],
        },
        "goal_projection": {
            "goals": [
                {"type": "satisfy_intent", "target": "restore_connectivity"},
            ],
        },
        "fact_projection": {"items": []},
        "entity_projection": {"items": []},
    }


def test_fw3_candidate_work_uses_existing_semantic_projection_as_fallback():
    snapshot = {
        "facts": {
            "conversation_state_runtime": {
                "final_state": {},
                "semantic_projection_shadow": {
                    "semantic_projection": _semantic_projection(),
                },
            },
        },
        "response": "",
    }
    before = deepcopy(snapshot)

    mapped = map_operational_work(snapshot)
    firewall = mapped["semantic_firewall"]

    assert snapshot == before
    assert firewall["package"] == "FW-3"
    assert firewall["authority_mode"] == "semantic"
    assert firewall["semantic_usage"] is True
    assert firewall["legacy_usage"] is False
    assert firewall["selected_source"] == "semantic_projection"
    assert firewall["confidence"] == 0.91
    assert firewall["mixed_authority"] is False
    assert firewall["downstream_raw_payload_access"] is False


def test_fw3_candidate_work_rolls_back_atomically_when_projection_is_unavailable():
    snapshot = {
        "facts": {"conversation_state_runtime": {"final_state": {}}},
        "response": "No tengo internet.",
    }

    mapped = map_operational_work(snapshot)
    firewall = mapped["semantic_firewall"]

    assert mapped["selected_work"]["operation"] == "diagnose_connectivity_issue"
    assert firewall["authority_mode"] == "rollback"
    assert firewall["semantic_usage"] is False
    assert firewall["legacy_usage"] is True
    assert firewall["rollback"] is True
    assert firewall["failure_reason"] == "semantic_projection_unavailable"
    assert firewall["selected_source"] == "legacy_output"
    assert firewall["mixed_authority"] is False


def test_fw3_raw_payload_values_no_longer_influence_candidate_work():
    snapshot = {
        "facts": {
            "last_raw_payload": "La factura vino mal.",
            "conversation_state_runtime": {
                "last_raw_payload": "No tengo internet.",
                "final_state": {
                    "confirmed_facts": {
                        "last_raw_payload": "Cargue una denuncia.",
                    },
                },
            },
        },
        "response": "",
    }

    mapped = map_operational_work(snapshot)

    assert mapped["selected_work"]["operation"] == "no_operational_work_identified"
    assert mapped["semantic_firewall"]["selected_source"] == "none"
    assert mapped["semantic_firewall"]["failure_reason"] == (
        "semantic_and_legacy_sources_unavailable"
    )


def test_fw3_has_zero_firewall_violations_and_completed_package_is_retained():
    graph = build_authority_dependency_graph(ROOT)
    plan = build_semantic_firewall_refactoring_plan(ROOT)
    package = next(
        item for item in plan.migration_packages if item["package_id"] == "FW-3"
    )
    fw3_violations = [
        item
        for item in graph.semantic_firewall_audit
        if item.get("migration_package") == "FW-3"
        and item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
    ]

    assert fw3_violations == []
    assert package["consumer_count"] == 0
    assert package["consumer_ids"] == []
    assert package["disposition"] == "REPLACE_WITH_STRUCTURED_INPUT"
    # FW-11 resolved the 4 duplicate pre-Mission planning writes, dropping
    # the violation count from 30 to 26.
    assert plan.summary["violation_count"] == 26
