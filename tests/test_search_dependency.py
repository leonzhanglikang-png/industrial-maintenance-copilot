from backend.app.api.dependencies import get_retriever


def test_get_retriever_searches_demo_manual() -> None:
    get_retriever.cache_clear()
    retriever = get_retriever()

    results = retriever.search(
        "discharge pressure suction blockage",
        limit=1,
    )

    assert len(results) == 1
    assert results[0].chunk.source == "demo_pump_manual.md"
    assert "discharge pressure" in results[0].chunk.text.lower()
    assert results[0].chunk.page_number is None
    assert results[0].score > 0.0


def test_get_retriever_returns_cached_instance() -> None:
    get_retriever.cache_clear()

    first = get_retriever()
    second = get_retriever()

    assert first is second
