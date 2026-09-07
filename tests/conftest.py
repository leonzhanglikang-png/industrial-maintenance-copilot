"""Keep every test away from the developer's persistent corpus and model credentials."""

from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    from backend.app.api import dependencies
    from backend.app.core.config import get_settings
    from backend.app.main import app

    monkeypatch.setenv("CHUNK_STORE_PATH", str(tmp_path / "test-documents.sqlite3"))
    monkeypatch.setenv("ANSWER_GENERATOR", "extractive")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
    cached = (
        get_settings,
        dependencies.get_retriever,
        dependencies.get_answer_generator,
        dependencies.get_fault_history_tool,
        dependencies.get_sensor_analysis_tool,
    )
    for function in cached:
        function.cache_clear()
    app.state.limiter.clear()
    yield
    for function in cached:
        function.cache_clear()
