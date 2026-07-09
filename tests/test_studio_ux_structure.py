import json
import threading
from urllib.request import urlopen

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from aca_os.studio_ux_structure import STUDIO_UX_STRUCTURE_CONTRACT, build_studio_ux_structure
from tools.aca_web import build_server


def test_studio_ux_structure_is_declarative_and_light_operational():
    ux = build_studio_ux_structure(runtime_binding={"runtime": {"status": "ready"}})

    assert ux["contract"] == STUDIO_UX_STRUCTURE_CONTRACT
    assert ux["shell"]["layout"] == "sidebar_two_column_workspace"
    assert ux["shell"]["visual_direction"] == "clean_light_operational_dashboard"
    assert ux["theme"]["mode"] == "light"
    assert ux["theme"]["primary"] == "#2563eb"
    assert ux["metadata"]["business_logic"] == "runtime_only"
    assert ux["metadata"]["style_locked"] is False
    assert ux["metadata"]["structure_locked"] is True


def test_studio_ux_navigation_and_panels_cover_runtime_workflow():
    ux = build_studio_ux_structure()

    nav_ids = {item["id"] for item in ux["navigation"]}
    panel_ids = {panel["id"] for panel in ux["panels"]}

    assert {"studio", "simulation", "domain_packs", "trace", "metrics", "deploy"}.issubset(nav_ids)
    assert {"runtime_overview", "simulation_input", "execution_context", "last_output", "trace_metrics"}.issubset(panel_ids)
    assert all(panel["data_source"].startswith("/") for panel in ux["panels"])


def test_runtime_api_exposes_studio_ux_structure_with_runtime_binding():
    api = RuntimeEndpointAPI()

    ux = api.studio_ux_structure(root="examples/domain_packs")

    assert ux["contract"] == STUDIO_UX_STRUCTURE_CONTRACT
    assert ux["runtime_binding"]["contract"] == "studio_runtime_binding.v1"
    assert ux["runtime_binding"]["domain"]["pack_count"] >= 2


def test_rest_api_routes_studio_ux_structure():
    rest = RuntimeRESTAPI()

    response = rest.route("GET", "/studio/ux", query={"root": "examples/domain_packs"})

    assert response.status_code == 200
    assert response.payload["contract"] == STUDIO_UX_STRUCTURE_CONTRACT
    assert response.payload["runtime_binding"]["runtime"]["status"] == "ready"


def test_web_runtime_serves_structured_light_studio_shell():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/studio/ux?root=examples/domain_packs", timeout=5) as response:
            ux = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "app-shell" in studio_html
    assert "sidebar" in studio_html
    assert "Proceso y acciones" in studio_html
    assert "Contexto para el runtime" not in studio_html
    assert ux["contract"] == STUDIO_UX_STRUCTURE_CONTRACT
