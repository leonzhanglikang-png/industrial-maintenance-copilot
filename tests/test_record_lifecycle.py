from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    build_reranked_hybrid_index,
    get_fault_history_tool,
    get_retriever,
)
from backend.app.core.config import get_settings
from backend.app.infrastructure.chunk_store import SQLiteChunkStore
from backend.app.infrastructure.fault_store import SQLiteFaultStore
from backend.app.infrastructure.persistent_retriever import PersistentSearchIndex
from backend.app.main import create_app
from tests.test_persistent_retriever import make_chunk


def fault_payload(equipment_id="pump-real-001"):
    return {
        "equipment_id": equipment_id,
        "occurred_at": "2026-10-07",
        "symptom": "泵出口压力偏低",
        "cause": "检查发现过滤器堵塞",
        "corrective_action": "清理过滤器后复测",
        "resolved": True,
    }


def test_delete_seed_is_visible_to_other_readers_and_survives_restart(tmp_path):
    path = tmp_path / "lifecycle.sqlite3"
    seed = make_chunk()

    def open_index():
        return PersistentSearchIndex(SQLiteChunkStore(path), build_reranked_hybrid_index, [seed])

    writer, reader = open_index(), open_index()
    assert writer.delete_document(seed.document_id) == 1
    assert reader.search("compressor") == []
    assert open_index().list_documents() == []
    assert reader.delete_document(seed.document_id) == 0
    # Explicit re-upload restores the document; automatic seeds cannot do so.
    assert writer.add_chunks([seed]) == 1
    assert reader.search("compressor")[0].chunk == seed


def test_document_api_removes_only_selected_document_after_restart():
    client = TestClient(create_app())
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("expired.txt", b"nebular compressor filter retirement")},
    ).json()
    document_id = upload["document_id"]
    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.json()["deleted_chunk_count"] == 1
    assert client.delete(f"/api/v1/documents/{document_id}").status_code == 404
    get_retriever.cache_clear()
    restarted = TestClient(create_app())
    documents = restarted.get("/api/v1/documents").json()["documents"]
    assert all(item["document_id"] != document_id for item in documents)
    assert any(item["source"] == "demo_pump_manual.md" for item in documents)
    results = restarted.post(
        "/api/v1/search", json={"query": "nebular compressor filter", "limit": 10}
    ).json()["results"]
    assert all(item["document_id"] != document_id for item in results)


def test_fault_created_in_workbench_is_persistent_and_used_by_agent():
    client = TestClient(create_app())
    # Warm the Agent dependency before adding a record: it must not cache old history.
    get_fault_history_tool()
    response = client.post("/api/v1/faults", json=fault_payload(" Pump-REAL-001 "))
    assert response.status_code == 201
    assert response.json()["is_demo"] is False
    record_id = response.json()["fault_id"]
    get_fault_history_tool.cache_clear()
    client = TestClient(create_app())
    history = client.get("/api/v1/faults", params={"equipment_id": "pump-real-001"}).json()
    assert [record["fault_id"] for record in history] == [record_id]
    assert client.get("/api/v1/faults", params={"equipment_id": "other-pump"}).json() == []
    agent = client.post(
        "/api/v1/agent/runs",
        json={"query": "pump pressure", "equipment_id": "PUMP-real-001"},
    ).json()
    assert agent["tool_trace"][1]["output"]["records"][0]["fault_id"] == record_id


def test_fault_input_validation_and_shared_token_protection(monkeypatch):
    client = TestClient(create_app())
    for field in ("equipment_id", "symptom", "cause", "corrective_action"):
        payload = {**fault_payload(), field: "   "}
        assert client.post("/api/v1/faults", json=payload).status_code == 422
    assert client.get("/api/v1/faults", params={"equipment_id": "  "}).status_code == 422
    monkeypatch.setenv("API_ACCESS_TOKEN", "test-only-not-a-production-token")
    get_settings.cache_clear()
    protected = TestClient(create_app())
    assert protected.post("/api/v1/faults", json=fault_payload()).status_code == 401
    assert protected.get("/api/v1/faults?equipment_id=pump-001").status_code == 401
    assert protected.delete("/api/v1/documents/unknown").status_code == 401


def test_concurrent_fault_writes_and_demo_provenance_survive_restart():
    client = TestClient(create_app())
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(
            executor.map(lambda _: client.post("/api/v1/faults", json=fault_payload()), range(8))
        )
    assert all(response.status_code == 201 for response in responses)
    ids = {response.json()["fault_id"] for response in responses}
    assert len(ids) == 8
    get_fault_history_tool.cache_clear()
    history = client.get("/api/v1/faults?equipment_id=pump-real-001").json()
    assert {record["fault_id"] for record in history} == ids
    seeds = client.get("/api/v1/faults?equipment_id=pump-001").json()
    assert len(seeds) == 2
    assert all(record["is_demo"] for record in seeds)


def test_concurrent_initialization_claims_demo_import_once(tmp_path):
    from backend.app.domain.agent import FaultRecord

    seed = FaultRecord(fault_id="seed", **fault_payload())
    path = tmp_path / "parallel-init.sqlite3"
    with ThreadPoolExecutor(max_workers=8) as executor:
        stores = list(executor.map(lambda _: SQLiteFaultStore(path, [seed]), range(16)))
    assert len(stores[0].lookup(seed.equipment_id)) == 1
