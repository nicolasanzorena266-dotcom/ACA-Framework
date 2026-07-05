from pathlib import Path
import json
import threading
from urllib.request import urlopen

from aca_os.public_demo_ux_qa import (
    PUBLIC_DEMO_UX_QA_CONTRACT,
    PUBLIC_DEMO_UX_QA_VALIDATION,
    build_public_demo_ux_qa,
    validate_public_demo_ux_qa,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from tools.aca_web import build_server


def test_public_demo_ux_qa_contract_covers_first_user_experience():
    report = build_public_demo_ux_qa(public_base_url="https://aca-public-web-demo.onrender.com")

    assert report["contract"] == PUBLIC_DEMO_UX_QA_CONTRACT
    assert report["product"]["name"] == "ACA Studio"
    assert report["product"]["experience_goal"] == "first_user_can_run_demo_and_understand_runtime_state"
    assert report["copy_baseline"]["primary_action"] == "Ejecutar demo"
    assert report["qa_summary"]["external_ai_required"] is False
    assert report["qa_summary"]["business_logic_location"] == "runtime"
    assert report["qa_summary"]["trace_visible"] is True
    assert report["qa_summary"]["domain_pack_visible"] is True


def test_public_demo_ux_qa_has_required_areas_and_routes():
    report = build_public_demo_ux_qa()

    areas = set(report["qa_summary"]["areas"])
    check_ids = {check["id"] for check in report["checks"]}

    assert {"landing", "first_run", "runtime_state", "domain_packs", "observability", "errors", "architecture"}.issubset(areas)
    assert {"landing_identity", "primary_action_visible", "business_logic_boundary"}.issubset(check_ids)
    assert report["entry_points"]["studio"] == "/studio"
    assert report["entry_points"]["ux_qa"] == "/public-demo/ux-qa"


def test_public_demo_ux_qa_validation_rejects_studio_business_logic():
    report = build_public_demo_ux_qa()
    report["qa_summary"]["business_logic_location"] = "studio"

    validation = validate_public_demo_ux_qa(report=report)

    assert validation["contract"] == PUBLIC_DEMO_UX_QA_VALIDATION
    assert validation["valid"] is False
    assert "public demo UX QA must keep business logic in runtime" in validation["errors"]


def test_public_demo_ux_qa_validation_checks_project_files():
    validation = validate_public_demo_ux_qa(project_root=Path("."))

    assert validation["valid"] is True
    assert "studio/index.html" in validation["checked_files"]
    assert validation["errors"] == []


def test_runtime_api_catalog_exposes_public_demo_ux_qa():
    api = RuntimeEndpointAPI()
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/public-demo/ux-qa" in paths
    assert "/public-demo/ux-qa/validate" in paths
    assert api.public_demo_ux_qa()["contract"] == PUBLIC_DEMO_UX_QA_CONTRACT
    assert api.validate_public_demo_ux_qa(project_root=".")["valid"] is True


def test_rest_api_exposes_public_demo_ux_qa():
    rest = RuntimeRESTAPI()

    report = rest.route("GET", "/public-demo/ux-qa")
    validation = rest.route("GET", "/public-demo/ux-qa/validate")

    assert report.status_code == 200
    assert report.payload["contract"] == PUBLIC_DEMO_UX_QA_CONTRACT
    assert validation.status_code == 200
    assert validation.payload["valid"] is True


def test_web_runtime_serves_public_demo_ux_qa_shell():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/public-demo/ux-qa", timeout=5) as response:
            qa = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Demo Polish / UX QA" in studio_html
    assert "/public-demo/ux-qa" in studio_html
    assert qa["contract"] == PUBLIC_DEMO_UX_QA_CONTRACT
