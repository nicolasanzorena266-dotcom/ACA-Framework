from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.plugins.rules.default_registry import build_default_registry

def test_kernel_runs_auto_claim_graph():
    kernel = ACAKernel(build_default_registry())
    graph = GraphCompiler().compile(Event(type="user_message", payload="Me chocaron ayer"))
    state = kernel.run(Event(type="user_message", payload="Me chocaron ayer"), graph)
    assert state.facts["event_type"] == "vehicle_collision"
    assert state.response
