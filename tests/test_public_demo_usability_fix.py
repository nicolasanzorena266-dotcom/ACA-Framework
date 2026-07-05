import json
import threading
from urllib.request import Request, urlopen

from aca_os.public_demo_usability import (
    PUBLIC_DEMO_THOUGHT_CONTRACT,
    PUBLIC_DEMO_USABILITY_CONTRACT,
    build_public_demo_thought_view,
    build_public_demo_usability,
    validate_public_demo_usability,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from tools.aca_web import build_server


def test_public_demo_usability_contract_hides_raw_json_and_code_by_default():
    spec = build_public_demo_usability()

    assert spec["contract"] == PUBLIC_DEMO_USABILITY_CONTRACT
    assert spec["rules"]["raw_json_default_visible"] is False
    assert spec["rules"]["code_visible_in_public_ui"] is False
    assert spec["rules"]["thought_view"] == "modal_only"
    assert spec["rules"]["buttons_must_have_actions"] is True
    assert spec["rules"]["business_logic_location"] == "runtime"
    assert spec["rules"]["external_ai_required"] is False


def test_public_demo_usability_button_contract_has_real_actions():
    spec = build_public_demo_usability()
    actions = spec["button_actions"]

    for label in [
        "Studio",
        "Simulación",
        "Domain Packs",
        "Trace",
        "Métricas",
        "Deploy",
        "customer_support",
        "operations_basic",
        "runtime_demo",
        "Ejecutar demo",
        "Ver diagnóstico",
        "Ver pensamiento",
        "Refrescar",
    ]:
        assert label in actions
        assert actions[label]


def test_public_demo_thought_view_is_human_readable_not_code_dump():
    thought = build_public_demo_thought_view(
        execution={
            "message": "Contame qué podés hacer",
            "matched_intent": {"name": "runtime.capabilities", "confidence": 1.0},
            "domain": {"pack": "runtime_demo"},
            "selected_flow": {"name": "explain_runtime_capabilities"},
            "trace_summary": {"trace_id": "t-1"},
        }
    )

    assert thought["contract"] == PUBLIC_DEMO_THOUGHT_CONTRACT
    assert thought["code_visible"] is False
    assert thought["raw_json_default_visible"] is False
    assert {step["id"] for step in thought["steps"]} >= {"input", "intent", "domain", "flow", "confidence", "trace"}


def test_public_demo_usability_validation_rejects_json_wall():
    spec = build_public_demo_usability()
    spec["rules"]["raw_json_default_visible"] = True

    validation = validate_public_demo_usability(spec=spec)

    assert validation["valid"] is False
    assert "raw JSON must not be visible by default" in validation["errors"]


def test_runtime_api_and_rest_expose_public_demo_usability():
    api = RuntimeEndpointAPI()
    rest = RuntimeRESTAPI()

    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}
    assert "/public-demo/usability" in paths
    assert "/public-demo/usability/validate" in paths
    assert "/public-demo/thought" in paths

    response = rest.route("GET", "/public-demo/usability")
    validation = rest.route("GET", "/public-demo/usability/validate")
    thought = rest.route(
        "POST",
        "/public-demo/thought",
        body={"message": "Hola", "matched_intent": {"name": "greeting"}},
    )

    assert response.status_code == 200
    assert response.payload["contract"] == PUBLIC_DEMO_USABILITY_CONTRACT
    assert validation.payload["valid"] is True
    assert thought.payload["contract"] == PUBLIC_DEMO_THOUGHT_CONTRACT


def test_public_studio_shell_uses_human_runtime_reading_and_modal_thought():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "Lectura humana del runtime" in html
    assert "Ver pensamiento" in html
    assert "modalBackdrop" in html
    assert "modalClose" in html
    assert "ACA Hosted" in html
    assert "Lectura humana del runtime" in html
    assert "Copiar resumen" in html
    assert "Ver diagnóstico" in html
    assert "openThought" in html
    assert "openDomainPacks" in html
    assert "openDeploy" in html
    assert "code_exposed: false" in html or "code_exposed" in html


def test_web_runtime_serves_usability_shell_and_endpoint():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/public-demo/usability", timeout=5) as response:
            usability = json.loads(response.read().decode("utf-8"))
        request = Request(
            f"http://{host}:{port}/public-demo/thought",
            data=json.dumps({"message": "Contame qué podés hacer"}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            thought = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Lectura humana del runtime" in studio_html
    assert "Ver pensamiento" in studio_html
    assert usability["contract"] == PUBLIC_DEMO_USABILITY_CONTRACT
    assert thought["contract"] == PUBLIC_DEMO_THOUGHT_CONTRACT
