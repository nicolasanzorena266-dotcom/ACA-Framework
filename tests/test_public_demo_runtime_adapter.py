import json
import subprocess
import sys

from aca_os.public_demo_runtime_adapter import (
    build_public_demo_runtime_adapter,
    build_public_demo_runtime_adapter_from_env,
    validate_public_demo_runtime_adapter,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_public_demo_runtime_adapter_describes_public_binding():
    adapter = build_public_demo_runtime_adapter(public_base_url="https://aca.example.com", fallback_port=9102)

    assert adapter["contract"] == "public_demo_runtime_adapter.v1"
    assert adapter["binding"]["host"] == "0.0.0.0"
    assert adapter["binding"]["startup_command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert adapter["binding"]["fallback_port"] == 9102
    assert adapter["runtime"]["business_logic_location"] == "runtime"
    assert adapter["runtime"]["interface_logic_location"] == "adapter"
    assert adapter["runtime"]["external_ai_required"] is False
    assert adapter["public_routes"]["runtime_adapter"] == "https://aca.example.com/public-demo/runtime-adapter"
    assert adapter["default_domain"]["pack_name"] == "customer_support"
    assert adapter["default_domain"]["demo_endpoint"] == "/demo/domain-flow"


def test_public_demo_runtime_adapter_normalizes_base_url_and_env():
    adapter = build_public_demo_runtime_adapter(public_base_url="https://aca.example.com/")

    assert adapter["public_base_url"] == "https://aca.example.com"
    assert adapter["public_routes"]["health"] == "https://aca.example.com/health"
    assert adapter["environment"]["ACA_PUBLIC_BASE_URL"] == "https://aca.example.com"
    assert adapter["environment"]["ACA_DEFAULT_DOMAIN_PACK"] == "customer_support"


def test_public_demo_runtime_adapter_can_be_built_from_env():
    adapter = build_public_demo_runtime_adapter_from_env(
        {
            "ACA_PUBLIC_BASE_URL": "https://demo.example.com",
            "ACA_HOST": "0.0.0.0",
            "PORT": "9191",
            "ACA_DOMAIN_PACK_ROOT": "examples/domain_packs",
            "ACA_DEFAULT_DOMAIN_PACK": "operations_basic",
        }
    )

    assert adapter["public_base_url"] == "https://demo.example.com"
    assert adapter["binding"]["fallback_port"] == 9191
    assert adapter["default_domain"]["pack_name"] == "operations_basic"


def test_public_demo_runtime_adapter_rejects_invalid_config():
    for kwargs, expected in [
        ({"public_base_url": ""}, "public_base_url"),
        ({"host": ""}, "host"),
        ({"port_env": ""}, "port_env"),
        ({"fallback_port": 70000}, "fallback_port"),
        ({"default_domain_pack": ""}, "default_domain_pack"),
    ]:
        try:
            build_public_demo_runtime_adapter(**kwargs)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"Expected {kwargs} to fail")


def test_public_demo_runtime_adapter_validation_uses_readiness():
    validation = validate_public_demo_runtime_adapter(project_root=".")

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["readiness"]["ready"] is True
    assert validation["adapter"]["contract"] == "public_demo_runtime_adapter.v1"


def test_public_demo_runtime_adapter_validation_rejects_adapter_that_hides_logic_in_interface():
    adapter = build_public_demo_runtime_adapter()
    adapter["runtime"]["business_logic_location"] = "adapter"

    validation = validate_public_demo_runtime_adapter(project_root=".", adapter=adapter)

    assert validation["valid"] is False
    assert "runtime business logic must stay in runtime" in validation["errors"]


def test_runtime_api_catalog_exposes_public_demo_runtime_adapter_endpoints():
    api = RuntimeEndpointAPI()
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/public-demo/runtime-adapter" in paths
    assert "/public-demo/runtime-adapter/validate" in paths
    assert api.public_demo_runtime_adapter(public_base_url="https://aca.example.com")["public_routes"]["studio"] == "https://aca.example.com/studio"


def test_runtime_rest_exposes_public_demo_runtime_adapter_endpoint():
    response = RuntimeRESTAPI().route(
        "GET",
        "/public-demo/runtime-adapter",
        query={"public_base_url": "https://aca.example.com", "fallback_port": "9102"},
    )

    assert response.status_code == 200
    assert response.payload["contract"] == "public_demo_runtime_adapter.v1"
    assert response.payload["binding"]["fallback_port"] == 9102


def test_runtime_rest_exposes_public_demo_runtime_adapter_validation_endpoint():
    response = RuntimeRESTAPI().route("GET", "/public-demo/runtime-adapter/validate")

    assert response.status_code == 200
    assert response.payload["valid"] is True


def test_aca_public_demo_cli_prints_runtime_adapter():
    result = subprocess.run(
        [
            sys.executable,
            "tools/aca_public_demo.py",
            "--public-base-url",
            "https://aca.example.com",
            "--runtime-adapter",
            "--validate",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["valid"] is True
    assert payload["adapter"]["public_base_url"] == "https://aca.example.com"
    assert payload["adapter"]["contract"] == "public_demo_runtime_adapter.v1"
