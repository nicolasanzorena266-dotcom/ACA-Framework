from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime, process_message
from aca_os.studio import build_studio_intelligence, build_studio_view, export_studio_view


def test_runtime_exports_studio_view_with_runtime_intelligence_panels():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    view = runtime.studio_view().to_dict()

    assert view["title"] == "ACA Studio MVP"
    panel_ids = [panel["id"] for panel in view["panels"]]
    assert panel_ids == [
        "session",
        "runtime_health",
        "decision_graph",
        "metrics",
        "components",
        "component_registry",
        "timeline",
        "trace",
        "events",
    ]
    assert view["metadata"]["contract"] == "studio_view.v1"
    assert view["metadata"]["evolution_contract"] == "studio_runtime_intelligence.v1"


def test_studio_view_is_built_from_introspection_contract():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Necesito hablar con un asesor"))
    snapshot = runtime.inspect_runtime()

    view = build_studio_view(snapshot)

    assert view.runtime_id == snapshot.runtime_id
    assert view.status == snapshot.status
    assert len(view.panels) == 9


def test_studio_exports_json_and_html():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es la franquicia?"))

    json_export = runtime.export_studio(format="json")
    html_export = runtime.export_studio(format="html")

    assert '"ACA Studio MVP"' in json_export
    assert "Runtime Health" in json_export
    assert "Decision Graph" in html_export
    assert "<!doctype html>" in html_export
    assert "Raw Studio JSON" in html_export


def test_process_message_can_include_studio_view():
    result = process_message("Que es CLEAS?", include_studio=True)

    assert result["studio"]["title"] == "ACA Studio MVP"
    assert result["studio"]["metadata"]["source"] == "runtime_introspection_api"
    assert result["studio"]["metadata"]["read_only"] is True


def test_studio_intelligence_projects_decision_graph_and_registry():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    intelligence = build_studio_intelligence(runtime.inspect_runtime().to_dict())

    assert intelligence["runtime_health"]["status"] == "ready"
    assert intelligence["decision_graph"]["available"] is True
    assert intelligence["decision_graph"]["terminal_node"] == "execution.plan"
    assert intelligence["component_registry"]["component_count"] >= 11
    assert "decision_graph.build" in intelligence["component_registry"]["capabilities"]


def test_studio_intelligence_uses_metrics_as_read_only_snapshot():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es la franquicia?"))

    intelligence = build_studio_intelligence(runtime.inspect_runtime().to_dict())

    assert intelligence["metrics"]["trace_count"] == 1
    assert intelligence["metrics"]["process_count"] == 1
    assert intelligence["metrics"]["process_duration_ms"]["count"] == 1
    assert intelligence["runtime_health"]["last_trace_duration_ms"] >= 0
