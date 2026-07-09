import json
import threading
from urllib.request import Request, urlopen

from aca_os.demo_domain_flow import (
    DEMO_DOMAIN_RUNTIME_FLOW_CONTRACT,
    DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT,
    DemoDomainRuntimeFlowRunner,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from tools.aca_web import build_server


def test_demo_domain_flow_scenario_contract_is_runtime_api_oriented():
    scenario = DemoDomainRuntimeFlowRunner().scenario_contract()

    assert scenario["contract"] == DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT
    assert scenario["domain_pack_root"] == "examples/domain_packs"
    assert "/demo/domain-flow" in {endpoint["path"] for endpoint in scenario["endpoints"]}
    assert scenario["metadata"]["domain_logic_embedded_in_interface"] is False


def test_demo_domain_flow_runs_customer_support_status_flow():
    result = DemoDomainRuntimeFlowRunner().run(
        message="Check ticket 12345 status",
        conversation_id="domain-demo-test",
    )

    assert result["contract"] == DEMO_DOMAIN_RUNTIME_FLOW_CONTRACT
    assert result["conversation_id"] == "domain-demo-test"
    assert result["domain"]["pack"] == "example.customer_support"
    assert result["matched_intent"]["name"] == "support.status_request"
    assert result["selected_flow"]["name"] == "support.case_status"
    assert result["entities"]["case_id"] == "12345"
    assert result["metadata"]["llm_used"] is False
    assert result["trace_summary"]["operation_count"] > 0


def test_demo_domain_flow_can_route_to_operations_pack_from_message():
    result = DemoDomainRuntimeFlowRunner().run(
        message="Where is the bottleneck in onboarding process?",
        conversation_id="operations-demo-test",
    )

    assert result["domain"]["pack"] == "example.operations_basic"
    assert result["matched_intent"]["name"] == "operations.process_review"
    assert result["selected_flow"]["name"] == "operations.review_process"
    assert "process_name" in result["entities"]


def test_runtime_api_exposes_demo_domain_flow_endpoints():
    api = RuntimeEndpointAPI()
    catalog = api.catalog()

    assert "/demo/domain-flow" in {endpoint["path"] for endpoint in catalog["endpoints"]}

    scenario = api.domain_flow_scenario()
    result = api.run_domain_flow(message="This is urgent, escalate ticket 7711 because client is blocked")

    assert scenario["contract"] == DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT
    assert result["matched_intent"]["name"] == "support.escalation_request"
    assert result["selected_flow"]["name"] == "support.escalation_triage"
    assert result["entities"]["case_id"] == "7711"
    assert result["entities"]["reason"] == "urgent_or_blocked_request"


def test_rest_api_routes_demo_domain_flow():
    rest = RuntimeRESTAPI()

    scenario = rest.route("GET", "/demo/domain-flow")
    result = rest.route(
        "POST",
        "/demo/domain-flow",
        body={"message": "What documents are missing for case 9988?", "conversation_id": "rest-domain-demo"},
    )

    assert scenario.status_code == 200
    assert scenario.payload["contract"] == DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT
    assert result.status_code == 200
    assert result.payload["contract"] == DEMO_DOMAIN_RUNTIME_FLOW_CONTRACT
    assert result.payload["conversation_id"] == "rest-domain-demo"
    assert result.payload["matched_intent"]["name"] == "support.missing_documentation"
    assert result.payload["selected_flow"]["name"] == "support.documentation_review"


def test_web_runtime_serves_demo_domain_flow_and_studio_binding_mentions_endpoint():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")

        with urlopen(f"http://{host}:{port}/demo/domain-flow", timeout=5) as response:
            scenario = json.loads(response.read().decode("utf-8"))

        request = Request(
            f"http://{host}:{port}/demo/domain-flow",
            data=json.dumps({"message": "Check ticket 555 status", "conversation_id": "web-domain-demo"}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "ACA Studio" in studio_html
    assert "Probar ejemplo" in studio_html
    assert "Run Demo Domain Flow" not in studio_html
    assert scenario["contract"] == DEMO_DOMAIN_RUNTIME_SCENARIO_CONTRACT
    assert result["contract"] == DEMO_DOMAIN_RUNTIME_FLOW_CONTRACT
    assert result["entities"]["case_id"] == "555"
