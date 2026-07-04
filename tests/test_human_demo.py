from aca_os.human_demo import HumanTestDemoRunner
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_human_demo_scenario_is_stable_and_interface_only():
    scenario = RuntimeEndpointAPI().human_demo_scenario()

    assert scenario["contract"] == "human_test_demo_scenario.v1"
    assert scenario["step_count"] == 3
    assert scenario["rules"]["business_logic"] == "runtime_only"
    assert scenario["rules"]["external_ai_required"] is False
    assert [step["id"] for step in scenario["steps"]] == [
        "concept-cleas",
        "human-escalation",
        "concept-franquicia",
    ]


def test_human_demo_run_uses_runtime_api_and_returns_human_summary():
    report = RuntimeEndpointAPI().run_human_demo(conversation_id="human-test")

    assert report["contract"] == "human_test_demo_run.v1"
    assert report["status"] == "passed"
    assert report["metadata"]["business_logic"] == "runtime_only"
    assert report["metadata"]["conversation_id"] == "human-test"
    assert len(report["steps"]) == 3
    assert {step["decision"] for step in report["steps"]} >= {"USE_TOOL", "ESCALATE"}
    assert all(step["trace_event_count"] > 0 for step in report["steps"])
    assert report["studio_state"]["contract"] == "studio_api_state.v1"


def test_human_demo_markdown_is_readable_without_runtime_internals():
    runner = HumanTestDemoRunner(requester=RuntimeEndpointAPI()._local_requester)

    markdown = runner.run_markdown(conversation_id="human-markdown")

    assert markdown.startswith("# ACA Human Test Demo")
    assert "Status: passed" in markdown
    assert "Business logic: runtime_only" in markdown
    assert "concept-cleas: passed" in markdown


def test_rest_exposes_human_demo_routes():
    rest = RuntimeRESTAPI()

    scenario = rest.route("GET", "/demo/human-test")
    report = rest.route("POST", "/demo/human-test", body={"conversation_id": "rest-demo"})
    markdown = rest.route("POST", "/demo/human-test", body={"format": "markdown"})

    assert scenario.status_code == 200
    assert scenario.payload["contract"] == "human_test_demo_scenario.v1"
    assert report.status_code == 200
    assert report.payload["status"] == "passed"
    assert report.payload["metadata"]["conversation_id"] == "rest-demo"
    assert markdown.status_code == 200
    assert isinstance(markdown.payload, str)
    assert "Status: passed" in markdown.payload
