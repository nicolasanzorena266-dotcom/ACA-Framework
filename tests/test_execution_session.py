from pathlib import Path

from aca_kernel.core.events import Event
from aca_os.session import ExecutionSession
from sdk.factory import build_galicia_runtime


def test_runtime_creates_serializable_execution_session(tmp_path: Path):
    runtime = build_galicia_runtime()
    runtime.process_output(Event(type="user_message", payload="Que es CLEAS?", metadata={"conversation_id": "s1"}))

    session = runtime.last_session()

    assert session is not None
    assert session.schema_version == "aca.session.v1"
    assert session.event["payload"] == "Que es CLEAS?"
    assert session.output["response"]
    assert session.trace["events"]


def test_execution_session_roundtrip_to_disk(tmp_path: Path):
    runtime = build_galicia_runtime()
    runtime.process_output(Event(type="user_message", payload="Que es la franquicia?"))
    path = tmp_path / "case_001.aca.json"

    runtime.save_last_session(str(path))
    loaded = ExecutionSession.load(path)

    assert loaded.summary()["event_type"] == "user_message"
    assert loaded.summary()["trace_event_count"] > 0
    assert loaded.replay_event().payload == "Que es la franquicia?"


def test_runtime_replays_saved_session_deterministically(tmp_path: Path):
    runtime = build_galicia_runtime()
    original = runtime.process_output(Event(type="user_message", payload="Que es CLEAS?"))
    path = tmp_path / "case_002.aca.json"
    runtime.save_last_session(str(path))

    replay_runtime = build_galicia_runtime()
    replayed = replay_runtime.replay_session(str(path))

    assert replayed.response == original.response
    assert replay_runtime.last_session() is not None


def test_execution_session_compare_reports_stable_decisions(tmp_path: Path):
    runtime = build_galicia_runtime()
    runtime.process_output(Event(type="user_message", payload="Que es CLEAS?"))
    left = runtime.last_session()
    runtime.process_output(Event(type="user_message", payload="Que es CLEAS?"))
    right = runtime.last_session()

    comparison = left.compare(right)

    assert comparison["same_response"] is True
    assert comparison["same_operations"] is True
