import json
import threading
from urllib.request import urlopen

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from aca_os.studio_visual_design import STUDIO_VISUAL_DESIGN_CONTRACT, build_studio_visual_design_system
from tools.aca_web import build_server


def test_studio_visual_design_system_locks_aca_studio_identity():
    design = build_studio_visual_design_system()

    assert design["contract"] == STUDIO_VISUAL_DESIGN_CONTRACT
    assert design["product"]["name"] == "ACA Studio"
    assert design["product"]["visual_direction"] == "clean_light_operational_cx_lab"
    assert design["metadata"]["business_logic"] == "runtime_only"
    assert design["metadata"]["style_locked"] is True
    assert design["metadata"]["name_locked"] == "ACA Studio"


def test_studio_visual_design_tokens_cover_light_dashboard_style():
    design = build_studio_visual_design_system()
    tokens = design["tokens"]

    assert tokens["color"]["background"] == "#f6f8fc"
    assert tokens["color"]["primary"] == "#2563eb"
    assert tokens["color"]["secondary"] == "#7c3aed"
    assert tokens["color"]["sidebar"] == "#ffffff"
    assert tokens["typography"]["font_family"].startswith("Inter")
    assert tokens["shape"]["radius_lg"] == "18px"
    assert tokens["elevation"]["card"].startswith("0 18px")


def test_studio_visual_design_components_are_declarative():
    design = build_studio_visual_design_system()

    component_ids = {component["id"] for component in design["components"]}
    assert {"sidebar", "metric_card", "simulation_phone", "context_panel", "primary_button"}.issubset(component_ids)
    assert all("tokens" in component for component in design["components"])
    assert all("runtime" not in component["tokens"] for component in design["components"])


def test_runtime_api_and_rest_expose_studio_visual_design():
    api = RuntimeEndpointAPI()
    rest = RuntimeRESTAPI()

    design = api.studio_visual_design()
    response = rest.route("GET", "/studio/design")

    assert design["contract"] == STUDIO_VISUAL_DESIGN_CONTRACT
    assert response.status_code == 200
    assert response.payload["contract"] == STUDIO_VISUAL_DESIGN_CONTRACT
    assert any(endpoint["path"] == "/studio/design" for endpoint in api.catalog()["endpoints"])


def test_studio_ux_embeds_design_system_without_owning_business_logic():
    api = RuntimeEndpointAPI()

    ux = api.studio_ux_structure(root="examples/domain_packs")

    assert ux["design_system"]["contract"] == STUDIO_VISUAL_DESIGN_CONTRACT
    assert ux["design_system"]["product"]["name"] == "ACA Studio"
    assert ux["metadata"]["business_logic"] == "runtime_only"
    assert ux["runtime_binding"]["contract"] == "studio_runtime_binding.v1"


def test_web_runtime_serves_visual_design_and_aca_studio_shell():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/studio/design", timeout=5) as response:
            design = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "ACA Studio" in studio_html
    assert "Visual Design System" in studio_html
    assert "/studio/design" in studio_html
    assert "brand-logo" in studio_html
    assert design["contract"] == STUDIO_VISUAL_DESIGN_CONTRACT
