import json
import subprocess
import sys

from aca_os.public_web_demo import build_public_web_demo_manifest, validate_public_web_demo_readiness
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_public_web_demo_manifest_describes_public_routes_and_startup():
    manifest = build_public_web_demo_manifest(public_base_url="https://aca.example.com", fallback_port=9101)

    assert manifest["contract"] == "public_web_demo_prep.v1"
    assert manifest["public_base_url"] == "https://aca.example.com"
    assert manifest["startup"]["command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert manifest["startup"]["port_env"] == "PORT"
    assert manifest["routes"]["studio"] == "https://aca.example.com/studio"
    assert manifest["routes"]["public_demo_readiness"] == "https://aca.example.com/public-demo/readiness"
    assert "/demo/domain-flow" in manifest["required_routes"]
    assert "tools/aca_public_demo.py" in manifest["required_files"]
    assert manifest["web_package"]["process"]["fallback_port"] == 9101


def test_public_web_demo_manifest_normalizes_base_url():
    manifest = build_public_web_demo_manifest(public_base_url="https://aca.example.com/")

    assert manifest["public_base_url"] == "https://aca.example.com"
    assert manifest["routes"]["health"] == "https://aca.example.com/health"


def test_public_web_demo_manifest_rejects_invalid_config():
    try:
        build_public_web_demo_manifest(public_base_url="")
    except ValueError as exc:
        assert "public_base_url" in str(exc)
    else:
        raise AssertionError("Expected missing public_base_url to fail")

    try:
        build_public_web_demo_manifest(default_domain_pack="")
    except ValueError as exc:
        assert "default_domain_pack" in str(exc)
    else:
        raise AssertionError("Expected missing default_domain_pack to fail")


def test_public_web_demo_readiness_validates_required_files():
    readiness = validate_public_web_demo_readiness(project_root=".")

    assert readiness["ready"] is True
    assert readiness["missing_files"] == []
    assert readiness["deploy_package_validation"]["valid"] is True
    assert readiness["manifest"]["contract"] == "public_web_demo_prep.v1"


def test_public_web_demo_readiness_reports_missing_files(tmp_path):
    readiness = validate_public_web_demo_readiness(project_root=tmp_path)

    assert readiness["ready"] is False
    assert "tools/aca_public_demo.py" in readiness["missing_files"]


def test_runtime_api_catalog_exposes_public_demo_endpoints():
    api = RuntimeEndpointAPI()
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/public-demo/manifest" in paths
    assert "/public-demo/readiness" in paths
    assert api.public_demo_manifest(public_base_url="https://aca.example.com")["routes"]["studio"] == "https://aca.example.com/studio"


def test_runtime_rest_exposes_public_demo_manifest_endpoint():
    response = RuntimeRESTAPI().route("GET", "/public-demo/manifest", query={"public_base_url": "https://aca.example.com"})

    assert response.status_code == 200
    assert response.payload["contract"] == "public_web_demo_prep.v1"
    assert response.payload["routes"]["health"] == "https://aca.example.com/health"


def test_runtime_rest_exposes_public_demo_readiness_endpoint():
    response = RuntimeRESTAPI().route("GET", "/public-demo/readiness")

    assert response.status_code == 200
    assert response.payload["ready"] is True


def test_aca_public_demo_cli_prints_and_validates_manifest():
    result = subprocess.run(
        [
            sys.executable,
            "tools/aca_public_demo.py",
            "--public-base-url",
            "https://aca.example.com",
            "--validate",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ready"] is True
    assert payload["manifest"]["public_base_url"] == "https://aca.example.com"


def test_static_public_web_demo_manifest_file_is_valid_json():
    with open("deploy/public-web-demo.json", "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["contract"] == "public_web_demo_prep.v1"
    assert payload["public_base_url"] == "https://aca-demo.example.com"
