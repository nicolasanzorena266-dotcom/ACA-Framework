import json
import os
import subprocess
import sys

from aca_os.deployable_web_package import build_deployable_web_package, validate_deployable_web_package
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_deployable_web_package_exposes_platform_startup_contract():
    package = build_deployable_web_package(app_name="aca-demo", fallback_port=9010)

    assert package["contract"] == "deployable_web_package.v1"
    assert package["app_name"] == "aca-demo"
    assert package["process"]["type"] == "web"
    assert package["process"]["command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert package["process"]["port_env"] == "PORT"
    assert package["process"]["fallback_port"] == 9010
    assert package["healthcheck"]["path"] == "/health"
    assert package["routes"]["studio"] == "/studio"
    assert package["routes"]["demo_domain_flow"] == "/demo/domain-flow"
    assert "tools/aca_web.py" in package["required_files"]
    assert package["local_runtime_plan"]["endpoints"]["studio"] == "http://127.0.0.1:9010/studio"


def test_deployable_web_package_rejects_invalid_config():
    try:
        build_deployable_web_package(port_env="")
    except ValueError as exc:
        assert "port_env" in str(exc)
    else:
        raise AssertionError("Expected missing port_env to fail")

    try:
        build_deployable_web_package(fallback_port=70000)
    except ValueError as exc:
        assert "fallback_port" in str(exc)
    else:
        raise AssertionError("Expected invalid fallback_port to fail")


def test_deployable_web_package_validation_checks_required_files():
    package = build_deployable_web_package()
    validation = validate_deployable_web_package(project_root=".", package=package)

    assert validation["valid"] is True
    assert validation["missing_files"] == []
    assert validation["package"]["contract"] == "deployable_web_package.v1"


def test_deployable_web_package_validation_reports_missing_files(tmp_path):
    package = build_deployable_web_package()
    validation = validate_deployable_web_package(project_root=tmp_path, package=package)

    assert validation["valid"] is False
    assert "tools/aca_web.py" in validation["missing_files"]


def test_runtime_api_exposes_deploy_package_catalog_and_payload():
    api = RuntimeEndpointAPI()
    catalog = api.catalog()
    paths = {endpoint["path"] for endpoint in catalog["endpoints"]}

    assert "/deploy/package" in paths
    assert "/deploy/validate" in paths
    assert api.deploy_package()["contract"] == "deployable_web_package.v1"


def test_runtime_rest_exposes_deploy_package_endpoint():
    response = RuntimeRESTAPI().route("GET", "/deploy/package", query={"fallback_port": "9100"})

    assert response.status_code == 200
    assert response.payload["contract"] == "deployable_web_package.v1"
    assert response.payload["process"]["fallback_port"] == 9100


def test_aca_deploy_cli_prints_and_validates_package():
    result = subprocess.run(
        [sys.executable, "tools/aca_deploy.py", "--app-name", "aca-demo", "--fallback-port", "9020", "--validate"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["valid"] is True
    assert payload["package"]["app_name"] == "aca-demo"
    assert payload["package"]["process"]["fallback_port"] == 9020


def test_aca_web_cli_uses_port_environment_for_print_plan():
    env = dict(os.environ)
    env["PORT"] = "9030"
    result = subprocess.run(
        [sys.executable, "tools/aca_web.py", "--print-plan"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["config"]["port"] == 9030
    assert payload["endpoints"]["studio"] == "http://127.0.0.1:9030/studio"
