from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_runtime_endpoint_api_loads_domain_packs_and_exposes_context():
    api = RuntimeEndpointAPI()

    loaded = api.load_domain_packs(root="examples/domain_packs")
    listed = api.domain_packs(root="examples/domain_packs")
    support = api.domain_pack("example.customer_support", root="examples/domain_packs")
    context = api.domain_context(root="examples/domain_packs")

    assert loaded["pack_count"] == 2
    assert listed["contract"] == "domain_pack_runtime.v1"
    assert support["pack"]["domain"] == "customer.support"
    assert context["domains"]["customer.support"]["assets"]["flows"]["schema"] == "aca.domain_pack.flows.v1"


def test_runtime_endpoint_catalog_includes_domain_pack_endpoints():
    api = RuntimeEndpointAPI()

    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/runtime/domain-packs" in paths
    assert "/runtime/domain-packs/load" in paths
    assert "/runtime/domain-context" in paths


def test_rest_domain_pack_routes_are_stable():
    api = RuntimeRESTAPI()

    loaded = api.route("POST", "/runtime/domain-packs/load", body={"root": "examples/domain_packs"})
    listed = api.route("GET", "/runtime/domain-packs", query={"root": "examples/domain_packs"})
    pack = api.route("GET", "/runtime/domain-packs/example.customer_support", query={"root": "examples/domain_packs"})
    context = api.route("GET", "/runtime/domain-context", query={"root": "examples/domain_packs"})

    assert loaded.status_code == 200
    assert loaded.payload["loaded_count"] == 2
    assert listed.payload["pack_count"] == 2
    assert pack.payload["pack"]["name"] == "example.customer_support"
    assert "domain.operations.metric_catalog" in context.payload["capabilities"]


def test_rest_domain_pack_errors_are_adapter_stable():
    api = RuntimeRESTAPI()

    missing_root = api.route("POST", "/runtime/domain-packs/load", body={})
    missing_pack = api.route("GET", "/runtime/domain-packs/nope", query={"root": "examples/domain_packs"})

    assert missing_root.status_code == 400
    assert missing_root.payload["error"]["code"] == "bad_request"
    assert missing_pack.status_code == 404
    assert missing_pack.payload["error"]["code"] == "not_found"
