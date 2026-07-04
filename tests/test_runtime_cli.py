import json
from pathlib import Path

from aca_os.runtime_cli import RuntimeCLI


def test_runtime_cli_status_uses_runtime_api():
    status = RuntimeCLI().status()

    assert status["status"] == "ready"
    assert status["component_count"] >= 10
    assert status["plugin_count"] == 0
    assert status["trace_count"] == 0


def test_runtime_cli_components_and_plugins_are_runtime_exports():
    cli = RuntimeCLI()

    components = cli.components()
    plugins = cli.plugins(root="examples/plugins")

    assert "components" in components
    assert plugins["plugin_count"] == 3
    assert {item["manifest"]["name"] for item in plugins["results"]} == {
        "example.context_snapshot",
        "example.decision_audit",
        "example.echo_tool",
    }


def test_runtime_cli_run_trace_metrics_and_introspection():
    cli = RuntimeCLI()

    result = cli.run(message="Que es CLEAS?", conversation_id="runtime-cli", include_trace=True)
    trace = cli.trace(message="Que es CLEAS?", conversation_id="runtime-cli-trace")
    metrics = cli.metrics(message="Que es CLEAS?", conversation_id="runtime-cli-metrics")
    introspection = cli.introspection(message="Que es CLEAS?", conversation_id="runtime-cli-inspect")

    assert result["conversation_id"] == "runtime-cli"
    assert result["execution_trace"]["events"]
    assert trace["conversation_id"] == "runtime-cli-trace"
    assert metrics["trace_count"] == 1
    assert introspection["last_state"]["conversation_id"] == "runtime-cli-inspect"


def test_runtime_cli_session_roundtrip(tmp_path: Path):
    cli = RuntimeCLI()
    path = tmp_path / "session.aca.json"

    saved = cli.save_session(message="Que es CLEAS?", output=path)
    shown = cli.show_session(path=path, summary=True)
    replayed = cli.replay_session(path=path)

    assert saved["status"] == "written"
    assert shown["trace_event_count"] > 0
    assert replayed["response"]


def test_runtime_cli_json_format_contract():
    rendered = RuntimeCLI().components(format="json")
    data = json.loads(rendered)

    assert "components" in data
