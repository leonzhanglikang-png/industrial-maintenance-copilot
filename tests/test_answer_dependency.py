from collections.abc import Generator

import pytest

import backend.app.api.dependencies as dependencies
from backend.app.core.config import Settings
from backend.app.infrastructure.answer_generators import ExtractiveAnswerGenerator
from backend.app.infrastructure.openai_answer_generator import (
    OpenAIResponsesAnswerGenerator,
)


@pytest.fixture(autouse=True)
def reset_generator_cache() -> Generator[None, None, None]:
    dependencies.get_answer_generator.cache_clear()
    yield
    dependencies.get_answer_generator.cache_clear()


def test_answer_generator_defaults_to_offline_extractive_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        answer_generator="extractive",
        _env_file=None,
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    generator = dependencies.get_answer_generator()

    assert isinstance(generator, ExtractiveAnswerGenerator)


def test_answer_generator_builds_openai_adapter_when_explicitly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        answer_generator="openai",
        llm_api_key="test-key",
        llm_model="test-model",
        _env_file=None,
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    generator = dependencies.get_answer_generator()

    assert isinstance(generator, OpenAIResponsesAnswerGenerator)


def test_openai_mode_rejects_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        answer_generator="openai",
        llm_api_key="",
        llm_model="",
        _env_file=None,
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    with pytest.raises(ValueError, match="LLM_API_KEY and LLM_MODEL"):
        dependencies.get_answer_generator()
