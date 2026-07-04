import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.component_registry import (
    ComponentDescriptor,
    ComponentRegistry,
    ComponentState,
)
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


class ExampleComponent:
    pass


def test_component_registry_registers_typed_metadata():
    registry = ComponentRegistry()

    descriptor = registry.register_instance(
        name="example",
        instance=ExampleComponent(),
        role="test component",
        capabilities=("example.run",),
        tags=("test",),
    )

    assert descriptor.name == "example"
    assert descriptor.class_name == "ExampleComponent"
    assert registry.require("example").capabilities == ("example.run",)
    assert registry.snapshot()["component_count"] == 1


def test_component_registry_enforces_lifecycle_transitions():
    registry = ComponentRegistry()
    registry.register(ComponentDescriptor(name="example", class_name="Example", role="test"))

    registry.initialize("example")
    active = registry.activate("example")

    assert active.state == ComponentState.ACTIVE
    with pytest.raises(ValueError):
        registry.initialize("example")


def test_component_registry_validates_declared_dependencies():
    registry = ComponentRegistry()

    with pytest.raises(ValueError):
        registry.register(
            ComponentDescriptor(
                name="plugin",
                class_name="Plugin",
                role="plugin",
                dependencies=("missing",),
            )
        )


def test_runtime_exports_component_registry_snapshot():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    components = runtime.export_components()

    assert components["component_count"] >= 11
    assert "active" in components["states"]
    assert "decision_graph_engine" in {item["name"] for item in components["components"]}
    assert "metrics_engine" in {item["name"] for item in components["components"]}


def test_introspection_reads_components_from_registry():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))
    snapshot = runtime.export_introspection()

    assert snapshot["component_registry"]["component_count"] == len(snapshot["components"])
    assert all(component["state"] == "active" for component in snapshot["components"])
    intent = next(item for item in snapshot["components"] if item["name"] == "intent_matcher")
    assert "intent.match" in intent["capabilities"]
