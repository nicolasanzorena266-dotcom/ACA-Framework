import json
from pathlib import Path


def test_web_demo_deployment_guide_exists_and_names_runtime_contract():
    guide = Path("docs/WEB_DEMO_DEPLOYMENT.md")

    assert guide.exists()
    text = guide.read_text(encoding="utf-8")

    assert "python tools/aca_web.py --host 0.0.0.0" in text
    assert "GET /health" in text
    assert "POST /demo/domain-flow" in text
    assert "examples/domain_packs" in text
    assert "External AI dependency: none" in text


def test_web_demo_deployment_guide_documents_local_smoke_path():
    text = Path("docs/WEB_DEMO_DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "python -m pytest -q" in text
    assert "python tools/aca_public_demo.py --validate --runtime-adapter" in text
    assert "http://127.0.0.1:8765/studio" in text
    assert "/public-demo/runtime-adapter" in text


def test_public_web_demo_config_references_deployment_guide():
    payload = json.loads(Path("deploy/public-web-demo.json").read_text(encoding="utf-8"))

    assert payload["documentation"]["deployment_guide"] == "docs/WEB_DEMO_DEPLOYMENT.md"
    assert payload["documentation"]["sprint_notes"] == "docs/SPRINT_56.md"
    assert payload["recommended_platform_contract"]["startup_command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert payload["recommended_platform_contract"]["healthcheck"] == "GET /health returns status ok"
    assert payload["recommended_platform_contract"]["external_ai_required"] is False


def test_public_web_demo_config_has_deployment_steps_and_acceptance():
    payload = json.loads(Path("deploy/public-web-demo.json").read_text(encoding="utf-8"))
    commands = {step["name"]: step["command"] for step in payload["deployment_steps"]}

    assert commands["Run tests"] == "python -m pytest -q"
    assert commands["Start web runtime locally"] == "python tools/aca_web.py --host 127.0.0.1 --port 8765 --open"
    assert commands["Start web runtime on platform"] == "python tools/aca_web.py --host 0.0.0.0"
    assert "GET /studio returns the Studio HTML shell" in payload["public_demo_acceptance"]
    assert "No web adapter contains domain business logic" in payload["public_demo_acceptance"]


def test_sprint_56_notes_keep_visual_design_out_of_scope():
    text = Path("docs/SPRINT_56.md").read_text(encoding="utf-8")

    assert "No visual redesign" in text
    assert "No hosted deployment yet" in text
    assert "No external AI dependency" in text
