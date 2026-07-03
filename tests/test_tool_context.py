from aca_os.context_manager import ContextManager
from aca_os.tool_engine import StaticKnowledgeAdapter, ToolEngine, ToolRequest
from aca_kernel.core.state import CognitiveState


def test_tool_engine_returns_structured_evidence():
    engine = ToolEngine()
    engine.register(StaticKnowledgeAdapter({"cleas": {"summary": "Convenio entre aseguradoras."}}))

    result = engine.execute(
        ToolRequest(
            tool_name="knowledge_base",
            intent="lookup_concept",
            payload={"key": "cleas"},
        )
    )

    assert result.success is True
    assert result.evidence["cleas"]["summary"] == "Convenio entre aseguradoras."


def test_context_manager_builds_minimal_bundle():
    state = CognitiveState(
        facts={"event_type": "vehicle_collision"},
        hypotheses={"needs_claim_guidance": 0.92},
        plan=["ask_if_injuries"],
        active_mission={"type": "auto_claim_guidance"},
    )

    bundle = ContextManager().build(
        state,
        memory={"preferred_style": "simple"},
        tool_evidence={"cleas": {"summary": "Convenio entre aseguradoras."}},
        domain_context={"domain": "galicia"},
    )

    data = bundle.to_dict()

    assert data["mission"]["type"] == "auto_claim_guidance"
    assert data["facts"]["event_type"] == "vehicle_collision"
    assert data["tool_evidence"]["cleas"]["summary"] == "Convenio entre aseguradoras."
    assert data["domain_context"]["domain"] == "galicia"
