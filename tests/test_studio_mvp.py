from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime, process_message
from aca_os.studio import build_studio_view, export_studio_view


def test_runtime_exports_studio_view_with_core_panels():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    view = runtime.studio_view().to_dict()

    assert view["title"] == "ACA Studio MVP"
    panel_ids = [panel["id"] for panel in view["panels"]]
    assert panel_ids == ["session", "components", "timeline", "trace", "events", "metrics"]
    assert view["metadata"]["contract"] == "studio_view.v1"


def test_studio_view_is_built_from_introspection_contract():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Necesito hablar con un asesor"))
    snapshot = runtime.inspect_runtime()

    view = build_studio_view(snapshot)

    assert view.runtime_id == snapshot.runtime_id
    assert view.status == snapshot.status
    assert len(view.panels) == 6


def test_studio_exports_json_and_html():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es la franquicia?"))

    json_export = runtime.export_studio(format="json")
    html_export = runtime.export_studio(format="html")

    assert '"ACA Studio MVP"' in json_export
    assert "<!doctype html>" in html_export
    assert "Raw Studio JSON" in html_export


def test_process_message_can_include_studio_view():
    result = process_message("Que es CLEAS?", include_studio=True)

    assert result["studio"]["title"] == "ACA Studio MVP"
    assert result["studio"]["metadata"]["source"] == "runtime_introspection_api"
