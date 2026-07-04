from aca_os.event_bus import EventBus, RuntimeEvent


def test_runtime_event_serializes_payload():
    event = RuntimeEvent(type="runtime.intent_matched", payload={"intent": "faq"})

    data = event.to_dict()

    assert data["type"] == "runtime.intent_matched"
    assert data["source"] == "runtime"
    assert data["payload"] == {"intent": "faq"}
    assert data["event_id"]
    assert data["timestamp"]


def test_event_bus_records_and_notifies_handlers():
    bus = EventBus()
    received = []

    bus.subscribe("runtime.action_planned", received.append)
    event = bus.publish("runtime.action_planned", {"action": "knowledge_lookup"})

    assert bus.events() == [event]
    assert received == [event]
    assert event.payload["action"] == "knowledge_lookup"


def test_event_bus_supports_wildcard_observers():
    bus = EventBus()
    received = []

    bus.subscribe("*", received.append)
    bus.publish("runtime.process.started")
    bus.publish("runtime.process.completed")

    assert [event.type for event in received] == [
        "runtime.process.started",
        "runtime.process.completed",
    ]
