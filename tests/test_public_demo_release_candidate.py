from __future__ import annotations

from pathlib import Path

from aca_os.public_demo_release_candidate import (
    PUBLIC_DEMO_RELEASE_CANDIDATE,
    PUBLIC_DEMO_RELEASE_CANDIDATE_VALIDATION,
    build_public_demo_release_candidate,
    validate_public_demo_release_candidate,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_build_public_demo_release_candidate_contract_targets_render_demo() -> None:
    candidate = build_public_demo_release_candidate(public_base_url="https://aca.example.test")

    assert candidate["contract"] == PUBLIC_DEMO_RELEASE_CANDIDATE
    assert candidate["status"] == "release-candidate"
    assert candidate["release"]["surface"] == "ACA Studio"
    assert candidate["release"]["external_ai_required"] is False
    assert candidate["entrypoints"]["studio"] == "https://aca.example.test/studio"
    assert candidate["render"]["start_command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert candidate["runtime"]["business_logic_location"] == "runtime"
    assert {gate["id"] for gate in candidate["release_gates"]} >= {
        "render_config_valid",
        "hosted_healthcheck_valid",
        "studio_assets_valid",
        "runtime_hardening_valid",
        "ux_qa_valid",
        "first_public_demo_valid",
        "public_url_smoke_ready",
    }


def test_validate_public_demo_release_candidate_uses_project_artifacts() -> None:
    validation = validate_public_demo_release_candidate(project_root=".")

    assert validation["contract"] == PUBLIC_DEMO_RELEASE_CANDIDATE_VALIDATION
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["missing_files"] == []
    assert all(validation["checks"].values())


def test_runtime_endpoint_api_exposes_public_demo_release_candidate() -> None:
    api = RuntimeEndpointAPI()

    candidate = api.public_demo_release_candidate(public_base_url="https://aca.example.test")
    validation = api.validate_public_demo_release_candidate(project_root=".")
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert candidate["contract"] == PUBLIC_DEMO_RELEASE_CANDIDATE
    assert validation["valid"] is True
    assert "/public-demo/release-candidate" in paths
    assert "/public-demo/release-candidate/validate" in paths


def test_runtime_rest_routes_public_demo_release_candidate() -> None:
    rest = RuntimeRESTAPI()

    candidate = rest.route("GET", "/public-demo/release-candidate", query={"public_base_url": "https://aca.example.test"})
    validation = rest.route("GET", "/public-demo/release-candidate/validate")

    assert candidate.status_code == 200
    assert candidate.payload["contract"] == PUBLIC_DEMO_RELEASE_CANDIDATE
    assert candidate.payload["entrypoints"]["health"] == "https://aca.example.test/health"
    assert validation.status_code == 200
    assert validation.payload["valid"] is True


def test_public_demo_release_candidate_config_and_docs_are_present() -> None:
    config = Path("deploy/public-demo-release-candidate.json")
    docs = Path("docs/PUBLIC_DEMO_RELEASE_CANDIDATE.md")

    assert config.exists()
    assert docs.exists()
    assert PUBLIC_DEMO_RELEASE_CANDIDATE in config.read_text(encoding="utf-8")
    assert "python tools/aca_smoke_url.py" in docs.read_text(encoding="utf-8")


def test_public_demo_release_candidate_rejects_invalid_payload() -> None:
    validation = validate_public_demo_release_candidate(
        candidate={
            "contract": "wrong",
            "status": "draft",
            "release": {"surface": "Other", "external_ai_required": True, "deterministic_runtime": False},
            "release_gates": [],
        }
    )

    assert validation["valid"] is False
    assert "invalid public demo release candidate contract" in validation["errors"]
    assert any(error.startswith("missing required release gate") for error in validation["errors"])
