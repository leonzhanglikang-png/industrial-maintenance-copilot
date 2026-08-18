from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_search_returns_ranked_result_with_citation() -> None:
    response = client.post(
        "/api/v1/search",
        json={
            "query": "discharge pressure suction blockage",
            "limit": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["query"] == "discharge pressure suction blockage"
    assert len(body["results"]) == 1

    result = body["results"][0]
    assert result["source"] == "demo_pump_manual.md"
    assert "discharge pressure" in result["text"].lower()
    assert result["page_number"] is None
    assert result["score"] > 0.0


def test_search_normalizes_query() -> None:
    response = client.post(
        "/api/v1/search",
        json={
            "query": "  pump pressure  ",
            "limit": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["query"] == "pump pressure"


def test_search_rejects_invalid_request() -> None:
    response = client.post(
        "/api/v1/search",
        json={
            "query": "   ",
            "limit": 0,
        },
    )

    assert response.status_code == 422
