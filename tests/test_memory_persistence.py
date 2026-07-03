from aca_os.memory_engine import MemoryEngine
from aca_os.memory_store import JsonMemoryStore


def test_memory_engine_persists_semantic_memory(tmp_path):
    path = tmp_path / "memory.json"

    engine = MemoryEngine(store=JsonMemoryStore(path))
    engine.remember_semantic("preferred_style", "simple")

    reloaded = MemoryEngine(store=JsonMemoryStore(path))

    assert reloaded.semantic["preferred_style"] == "simple"


def test_memory_engine_persists_episodic_memory(tmp_path):
    path = tmp_path / "memory.json"

    engine = MemoryEngine(store=JsonMemoryStore(path))
    engine.remember_episodic(
        key="mission",
        value={"type": "auto_claim_guidance"},
        source="test",
        relevance=0.9,
    )

    reloaded = MemoryEngine(store=JsonMemoryStore(path))

    assert len(reloaded.episodic) == 1
    assert reloaded.episodic[0].key == "mission"
    assert reloaded.episodic[0].value["type"] == "auto_claim_guidance"