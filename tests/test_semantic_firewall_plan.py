import json
import subprocess
import sys
from pathlib import Path

import pytest

from aca_os.semantic_firewall_plan import build_semantic_firewall_refactoring_plan


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    return build_semantic_firewall_refactoring_plan(ROOT)


def test_plan_is_reproducible_and_preserves_authority_graph_fingerprint(plan):
    second = build_semantic_firewall_refactoring_plan(ROOT)

    assert plan.plan_hash == second.plan_hash
    assert plan.authority_source_hash == second.authority_source_hash
    assert plan.authority_graph_hash == second.authority_graph_hash
    assert plan.summary["effective_authority"] == "legacy"
    assert plan.summary["behavior_change"] is False
    assert json.loads(json.dumps(plan.to_dict()))["contract"] == (
        "semantic_firewall_refactoring_plan.v1"
    )


def test_inventory_covers_every_discovered_text_access_and_replacement(plan):
    # FW-11 collapsed the premature pre-Mission write in
    # ConversationManager.begin_turn, removing its 4 duplicate BLOCKER-severity
    # text-access consumers (one per artifact: CIM, InformationGainPlan,
    # ConversationPlan, ConversationResponsePlan).
    assert plan.summary["text_access_count"] == 33
    assert plan.summary["allowed_access_count"] == 5
    assert plan.summary["legacy_prefirewall_compatibility_count"] == 2
    assert plan.summary["violation_count"] == 26
    assert plan.summary["replacement_coverage"] == 1.0
    assert len({item["consumer_id"] for item in plan.inventory}) == 33
    assert all(item["semantic_replacement_field"] for item in plan.inventory)
    assert all(item["migration_package"] for item in plan.inventory)
    assert all(item["rollback"] for item in plan.inventory)


def test_inventory_classifies_critical_consumers_and_legal_boundaries(plan):
    blockers = [item for item in plan.inventory if item["severity"] == "BLOCKER"]
    allowed = [
        item for item in plan.inventory if item["classification"] == "ALLOWED_TEXT_ACCESS"
    ]

    assert len(blockers) == 12
    assert {item["component"] for item in allowed} == {
        "conversation_manager",
        "runtime_timeline",
        "semantic_authority",
        "session",
    }
    assert all(item["disposition"] == "KEEP_ALLOWED" for item in allowed)
    assert all(item["migration_package"] == "FW-A0" for item in allowed)
    assert any(item["access_mode"] == "audit" for item in allowed)
    assert any(item["access_mode"] == "write" for item in allowed)
    assert plan.summary["access_role_distribution"]["comparison"] > 0
    assert plan.summary["access_role_distribution"]["debug"] == 0


def test_output_access_is_constrained_and_never_promoted(plan):
    output = [
        item
        for item in plan.inventory
        if item["component"] in {"narrative_response_composer", "llm_verbalizer"}
    ]

    assert len(output) == 2
    assert all(item["disposition"] == "KEEP_CONSTRAINED" for item in output)
    assert all(item["migration_package"] == "FW-2" for item in output)
    assert all("No promotion" in item["promotion_impact"] for item in output)


def test_every_consumer_belongs_to_one_deployable_package(plan):
    package_ids = {item["package_id"] for item in plan.migration_packages}
    members = [
        consumer_id
        for package in plan.migration_packages
        for consumer_id in package["consumer_ids"]
    ]

    assert package_ids == {
        "FW-A0", "FW-2", "FW-3", "FW-4", "FW-5", "FW-6", "FW-7", "FW-8",
        "FW-9", "FW-10", "FW-11", "FW-12", "FW-13", "FW-14", "FW-15", "FW-16",
    }
    assert sorted(members) == sorted(item["consumer_id"] for item in plan.inventory)
    assert all(package["acceptance"] for package in plan.migration_packages)
    assert all(package["rollback"] for package in plan.migration_packages)


def test_elimination_order_is_topological_and_risk_driven(plan):
    positions = {
        item["package_id"]: item["position"] for item in plan.elimination_order
    }
    packages = {item["package_id"]: item for item in plan.migration_packages}

    for package_id, package in packages.items():
        assert all(positions[dependency] < positions[package_id] for dependency in package["dependencies"])
    assert positions["FW-A0"] == 1
    assert positions["FW-3"] < positions["FW-5"]
    assert positions["FW-10"] < positions["FW-11"] < positions["FW-12"]
    assert positions["FW-15"] < positions["FW-16"]


def test_recomputation_subgraph_separates_overwrites_from_valid_lifecycles(plan):
    # FW-11 resolved: CIM, InformationGainPlan, ConversationPlan and
    # ConversationResponsePlan each have exactly one writer now, so there are
    # no more RECOMPUTED_AND_OVERWRITTEN records for them.
    # ACA-303 added ConversationalGoal's own GUARDED_MULTI_AUTHORITY record
    # (its atomic selector was previously invisible to this report), so the
    # non-overwrite record count is 5, not 4: cognitive_state, intent_match
    # and runtime_outcomes (MULTIPLE_WRITERS), plus ConversationalAct and
    # ConversationalGoal (GUARDED_MULTI_AUTHORITY).
    report = plan.recomputation_report
    actual_overwrites = [
        item for item in report["records"] if item["type"] == "RECOMPUTED_AND_OVERWRITTEN"
    ]

    assert report["record_count"] == 5
    assert report["actual_overwrite_count"] == 0
    assert actual_overwrites == []
    assert report["mermaid"].startswith("flowchart LR")


def test_dependency_collapse_identifies_only_conditional_removals(plan):
    candidates = {item["candidate"]: item for item in plan.dependency_collapse_candidates}

    assert len(candidates) == 6
    assert "Runtime post-Mission conversation planning block" in candidates
    assert "Plugin-local semantic analyzers" in candidates
    assert "IntentMatcher lexical implementation" in candidates
    assert "Duplicated /demo/domain-flow conversation pipeline" in candidates
    assert "OperationalWorkMapper._source_text fallback" not in candidates
    assert all(item["removal_condition"] for item in candidates.values())
    assert all(item["replacement"] for item in candidates.values())


def test_promotion_forecast_keeps_planners_policy_and_mission_in_their_authority(plan):
    forecast = {item["after_package"]: item for item in plan.promotion_forecast}

    assert forecast["FW-5"]["forecast_status"] == "PILOT_ELIGIBLE"
    assert forecast["FW-10"]["forecast_status"] == "UNBLOCKED_NOT_READY"
    assert forecast["FW-11"]["forecast_status"] == "PILOT_ELIGIBLE"
    assert forecast["FW-14"]["forecast_status"] == "FIREWALL_CLEAN_INDEPENDENT"
    assert forecast["FW-15"]["forecast_status"] == "FIREWALL_CLEAN_INDEPENDENT"
    assert forecast["FW-16"]["forecast_status"] == "SA_4_ENTRY_CRITERIA_MET"


def test_cli_exposes_machine_readable_reports_without_runtime_integration(plan):
    result = subprocess.run(
        [sys.executable, "tools/run_semantic_firewall_plan.py", "--format", "summary"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    runtime_source = (ROOT / "aca_os" / "runtime.py").read_text(encoding="utf-8")

    assert payload["plan_hash"] == plan.plan_hash
    assert payload["summary"]["violation_count"] == 26
    assert "semantic_firewall_plan" not in runtime_source
