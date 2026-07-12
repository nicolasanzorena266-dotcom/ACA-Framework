from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.plugins.rules.default_registry import build_default_registry

def test_kernel_runs_auto_claim_graph():
    kernel = ACAKernel(build_default_registry())
    graph = GraphCompiler().compile(Event(type="user_message", payload="Me chocaron ayer"))
    state = kernel.run(Event(type="user_message", payload="Me chocaron ayer"), graph)
    assert state.facts["event_type"] == "vehicle_collision"
    assert state.response


def test_compiler_obeys_execution_plan_over_text_reinterpretation():
    state = CognitiveState(
        facts={
            "zero_cost_execution_plan": {
                "flow": "static_response",
                "source_action": "static_response",
                "kernel_program": "greeting",
                "steps": [],
            }
        }
    )

    graph = GraphCompiler().compile(Event(type="user_message", payload="Me chocaron ayer"), state)

    assert graph.name == "greeting"
