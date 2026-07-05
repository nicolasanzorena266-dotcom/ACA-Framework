from __future__ import annotations

from pathlib import Path

from aca_os.render_deployment_config import (
    RENDER_DEPLOYMENT_CONFIG,
    RENDER_DEPLOYMENT_VALIDATION,
    build_render_deployment_config,
    render_blueprint_yaml,
    validate_render_deployment_config,
)


def test_build_render_deployment_config_targets_render_web_service() -> None:
    config = build_render_deployment_config(public_base_url="https://aca.example.onrender.com")

    assert config["contract"] == RENDER_DEPLOYMENT_CONFIG
    assert config["platform"] == "render"
    assert config["service"]["type"] == "web"
    assert config["service"]["runtime"] == "python"
    assert config["process"]["start_command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert config["process"]["healthcheck_path"] == "/health"
    assert config["process"]["port_env"] == "PORT"
    assert config["public_urls"]["studio"] == "https://aca.example.onrender.com/studio"
    assert config["environment"]["ACA_PUBLIC_BASE_URL"] == "https://aca.example.onrender.com"
    assert "render.yaml" in config["required_files"]


def test_render_blueprint_yaml_contains_render_required_fields() -> None:
    yaml_text = render_blueprint_yaml(build_render_deployment_config(service_name="aca-demo-test"))

    assert "services:" in yaml_text
    assert "type: web" in yaml_text
    assert "name: aca-demo-test" in yaml_text
    assert "runtime: python" in yaml_text
    assert "buildCommand: python -m pytest -q" in yaml_text
    assert "startCommand: python tools/aca_web.py --host 0.0.0.0" in yaml_text
    assert "healthCheckPath: /health" in yaml_text
    assert "key: ACA_PUBLIC_BASE_URL" in yaml_text


def test_validate_render_deployment_config_uses_repo_files() -> None:
    validation = validate_render_deployment_config(project_root=".")

    assert validation["contract"] == RENDER_DEPLOYMENT_VALIDATION
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["checks"]["render_yaml"] is True
    assert validation["checks"]["first_public_hosted_demo"] is True


def test_validate_render_deployment_config_rejects_bad_start_command() -> None:
    config = build_render_deployment_config()
    config["process"]["start_command"] = "python broken.py"

    validation = validate_render_deployment_config(project_root=".", config=config)

    assert validation["valid"] is False
    assert "Render start command must launch tools/aca_web.py" in validation["errors"]
    assert "Render start command must bind to 0.0.0.0" in validation["errors"]


def test_render_config_files_are_present() -> None:
    render_yaml = Path("render.yaml")
    deploy_json = Path("deploy/render-deployment.json")
    guide = Path("docs/RENDER_DEPLOYMENT.md")

    assert render_yaml.exists()
    assert deploy_json.exists()
    assert guide.exists()
    assert "healthCheckPath: /health" in render_yaml.read_text(encoding="utf-8")
    assert RENDER_DEPLOYMENT_CONFIG in deploy_json.read_text(encoding="utf-8")
    assert "Render free services may cold-start" in guide.read_text(encoding="utf-8")

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_runtime_endpoint_api_exposes_render_deployment_config() -> None:
    api = RuntimeEndpointAPI()

    config = api.render_deployment_config(public_base_url="https://aca.example.onrender.com")
    validation = api.validate_render_deployment_config(project_root=".")
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert config["contract"] == RENDER_DEPLOYMENT_CONFIG
    assert config["public_urls"]["health"] == "https://aca.example.onrender.com/health"
    assert validation["valid"] is True
    assert "/deploy/render" in paths
    assert "/deploy/render/validate" in paths


def test_runtime_rest_routes_render_deployment_config() -> None:
    rest = RuntimeRESTAPI()

    config = rest.route("GET", "/deploy/render", query={"public_base_url": "https://aca.example.onrender.com"})
    validation = rest.route("GET", "/deploy/render/validate")

    assert config.status_code == 200
    assert config.payload["contract"] == RENDER_DEPLOYMENT_CONFIG
    assert config.payload["public_urls"]["studio"] == "https://aca.example.onrender.com/studio"
    assert validation.status_code == 200
    assert validation.payload["valid"] is True
