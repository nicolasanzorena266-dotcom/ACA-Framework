from aca_os.evaluation import (
    load_operational_production_benchmark,
    render_operational_production_benchmark_report,
    run_operational_production_benchmark,
)
from aca_os.operational_tools import HandoffPackageAdapter
from aca_os.tool_engine import ToolEngine, ToolExecutionContext, ToolExecutionMode, ToolRequest


def test_handoff_package_tool_executes_real_write_with_receipt(tmp_path):
    store_path = tmp_path / "handoff_packages.jsonl"
    engine = ToolEngine()
    engine.register(HandoffPackageAdapter(store_path=store_path))

    result = engine.execute(
        ToolRequest(
            tool_name="handoff_package",
            intent="prepare_handoff_package",
            payload={
                "conversation_id": "production-test",
                "idempotency_key": "production-test-001",
                "selected_work": {"operation": "prepare_handoff"},
                "governance_assessment": {"execution_allowed": True},
                "ledger_record": {"conversation_id": "production-test"},
            },
        ),
        ToolExecutionContext(mode=ToolExecutionMode.OFFICIAL, runtime_engine="runtime_executor"),
    )

    receipt = result.evidence["external_receipt"]
    assert result.success is True
    assert result.execution["action"] == "execute"
    assert result.execution["executed"] is True
    assert receipt["status"] == "created"
    assert receipt["side_effects"] is True
    assert receipt["reversible"] is True
    assert store_path.exists()
    assert len(store_path.read_text(encoding="utf-8").splitlines()) == 1


def test_handoff_package_tool_is_idempotent(tmp_path):
    store_path = tmp_path / "handoff_packages.jsonl"
    engine = ToolEngine()
    engine.register(HandoffPackageAdapter(store_path=store_path))
    request = ToolRequest(
        tool_name="handoff_package",
        intent="prepare_handoff_package",
        payload={
            "conversation_id": "production-duplicate",
            "idempotency_key": "same-key",
            "selected_work": {"operation": "prepare_handoff"},
            "governance_assessment": {"execution_allowed": True},
            "ledger_record": {"conversation_id": "production-duplicate"},
        },
    )

    first = engine.execute(request, ToolExecutionContext(mode=ToolExecutionMode.OFFICIAL))
    second = engine.execute(request, ToolExecutionContext(mode=ToolExecutionMode.OFFICIAL))

    assert first.evidence["external_receipt"]["status"] == "created"
    assert second.evidence["external_receipt"]["status"] == "duplicate_replayed"
    assert len(store_path.read_text(encoding="utf-8").splitlines()) == 1


def test_operational_production_benchmark_loads_scenarios():
    suite = load_operational_production_benchmark()

    assert suite["contract"] == "operational_production_benchmark_suite.v1"
    assert suite["scenario_count"] >= 10
    assert suite["tool"] == "handoff_package"
    assert suite["operation"] == "prepare_handoff"


def test_operational_production_benchmark_executes_and_persists(tmp_path):
    result = run_operational_production_benchmark(
        scenario_ids=["PROD-001", "PROD-003", "PROD-006"],
        storage_root=tmp_path,
    )

    assert result["contract"] == "operational_production_benchmark_result.v1"
    assert result["scenario_count"] == 3
    assert result["quality"]["production_success_percentage"] == 100.0
    assert result["quality"]["real_execution_percentage"] == 100.0
    assert result["quality"]["ledger_persistence_percentage"] == 100.0
    assert result["quality"]["idempotency_accuracy_percentage"] == 100.0
    assert result["quality"]["ledger_consistency_percentage"] == 100.0
    assert (tmp_path / "PROD-001" / "operational_ledger.jsonl").exists()
    assert (tmp_path / "PROD-001" / "handoff_packages.jsonl").exists()


def test_operational_production_benchmark_report_is_renderable_markdown(tmp_path):
    result = run_operational_production_benchmark(
        scenario_ids=["PROD-001"],
        storage_root=tmp_path,
    )

    report = render_operational_production_benchmark_report(result)

    assert "# ACA Operational Production Benchmark" in report
    assert "Real execution" in report
    assert "`PROD-001`" in report
    assert "state=executed" in report
