import json
import threading
from urllib.request import urlopen

from aca_os.public_demo_polish import (
    PUBLIC_DEMO_POLISH_CONTRACT,
    build_public_demo_polish,
    validate_public_demo_polish,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from tools.aca_web import build_server


def test_public_demo_polish_contract_keeps_studio_public_demo_clear():
    polish = build_public_demo_polish()

    assert polish["contract"] == PUBLIC_DEMO_POLISH_CONTRACT
    assert polish["product"]["name"] == "ACA Studio"
    assert polish["hero"]["title"] == "Probá ACA Studio con un dominio cargado."
    assert polish["states"]["ready"] == "Runtime listo"
    assert polish["public_demo_checks"]["external_ai_required"] is False
    assert polish["metadata"]["business_logic"] == "runtime_only"


def test_public_demo_polish_has_safe_demo_prompts_and_output_panels():
    polish = build_public_demo_polish()

    prompt_ids = {prompt["id"] for prompt in polish["prompts"]}
    panel_ids = {panel["id"] for panel in polish["output_panels"]}

    assert {"ticket_status", "pending_docs", "ops_followup"}.issubset(prompt_ids)
    assert {"runtime_output", "domain_context", "trace_metrics"}.issubset(panel_ids)
    assert all(prompt["domain_pack"] in {"customer_support", "operations_basic"} for prompt in polish["prompts"])


def test_public_demo_polish_validation_rejects_interface_business_logic():
    polish = build_public_demo_polish()
    polish["public_demo_checks"]["business_logic_location"] = "studio_shell"

    validation = validate_public_demo_polish(polish)

    assert validation["valid"] is False
    assert "runtime business logic must stay in runtime" in validation["errors"]


def test_runtime_api_catalog_exposes_public_demo_polish_endpoints():
    api = RuntimeEndpointAPI()
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/public-demo/polish" in paths
    assert "/public-demo/polish/validate" in paths
    assert api.public_demo_polish()["contract"] == PUBLIC_DEMO_POLISH_CONTRACT
    assert api.validate_public_demo_polish()["valid"] is True


def test_runtime_rest_exposes_public_demo_polish():
    rest = RuntimeRESTAPI()

    polish_response = rest.route("GET", "/public-demo/polish")
    validation_response = rest.route("GET", "/public-demo/polish/validate")

    assert polish_response.status_code == 200
    assert polish_response.payload["contract"] == PUBLIC_DEMO_POLISH_CONTRACT
    assert validation_response.status_code == 200
    assert validation_response.payload["valid"] is True


def test_web_runtime_serves_polished_public_demo_shell():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/public-demo/polish", timeout=5) as response:
            polish = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Probar ejemplo" in studio_html
    assert "Calidad de experiencia" in studio_html
    assert "Demo Polish" not in studio_html
    assert "/public-demo/polish" in studio_html
    assert polish["contract"] == PUBLIC_DEMO_POLISH_CONTRACT
