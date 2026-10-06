import json
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from backend.app.api import dependencies
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import CitationValidationError, ModelServiceError
from backend.app.domain.documents import Chunk
from backend.app.infrastructure.answer_generators import NO_EVIDENCE_ANSWER
from backend.app.infrastructure.chat_answer_generator import ChatCompletionsAnswerGenerator
from backend.app.main import create_app
from backend.app.ports.answering import AnswerGenerator
from backend.app.ports.retrieval import SearchResult
from backend.app.services.rag_answering import RagAnswerService


def evidence():
    return [
        SearchResult(
            chunk=Chunk(
                chunk_id=f"chunk-{index}",
                document_id="manual",
                chunk_index=index - 1,
                source="synthetic.md",
                text=text,
            ),
            score=0.9,
        )
        for index, text in enumerate(
            ["Inspect the suction line for blockage.", "Never run the pump dry."], start=1
        )
    ]


@contextmanager
def adapter(
    content="Inspect the inlet. [S1]",
    *,
    finish="stop",
    status=200,
    body=None,
    disable_thinking=True,
):
    calls = []

    def handler(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only-key"
        calls.append(json.loads(request.content))
        if status == "timeout":
            raise httpx.ReadTimeout("private-provider-body", request=request)
        payload = (
            body
            if body is not None
            else {
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": finish,
                        "message": {"role": "assistant", "content": content},
                    }
                ]
            }
        )
        return httpx.Response(status, json=payload)

    with OpenAI(
        api_key="test-only-key",
        base_url="https://api.deepseek.com",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as client:
        yield (
            ChatCompletionsAnswerGenerator(
                api_key="test-only-key",
                model="test-model",
                base_url="https://api.deepseek.com",
                max_tokens=512,
                disable_thinking=disable_thinking,
                client=client,
            ),
            calls,
        )


def test_chat_request_is_bounded_grounded_and_non_streaming():
    with adapter() as (generator, calls):
        assert isinstance(generator, AnswerGenerator)
        draft = generator.generate(" pressure ", evidence())
        assert draft.cited_chunk_ids == ["chunk-1"]
        assert draft.generation_method == "chat-completions:test-model"
        request = calls[0]
        assert request["model"] == "test-model"
        assert request["max_tokens"] == 512
        assert request["stream"] is False
        assert request["thinking"] == {"type": "disabled"}
        assert request["messages"][0]["role"] == "system"
        assert "untrusted data" in request["messages"][0]["content"]
        assert "Question:\npressure" in request["messages"][1]["content"]
        assert "[S2] source=synthetic.md" in request["messages"][1]["content"]
        assert "tools" not in request


def test_generic_compatible_mode_omits_deepseek_extension():
    with adapter(disable_thinking=False) as (generator, calls):
        generator.generate("pressure", evidence())
        assert "thinking" not in calls[0]


def test_no_evidence_and_blank_query_never_call_remote():
    with adapter() as (generator, calls):
        assert generator.generate("unknown", []).answer == NO_EVIDENCE_ANSWER
        with pytest.raises(ValueError, match="blank"):
            generator.generate(" ", evidence())
        assert calls == []


@pytest.mark.parametrize("content", ["", "  ", "No sources.", NO_EVIDENCE_ANSWER])
def test_uncited_answers_refuse(content):
    with adapter(content) as (generator, _):
        draft = generator.generate("pressure", evidence())
        assert draft.answer == NO_EVIDENCE_ANSWER
        assert draft.cited_chunk_ids == []


@pytest.mark.parametrize("content", ["Unsafe [S0]", "Unknown [S3]"])
def test_invalid_citations_are_rejected(content):
    with adapter(content) as (generator, _):
        with pytest.raises(CitationValidationError):
            generator.generate("pressure", evidence())


def test_citation_order_survives_rag_mapping():
    class Retriever:
        def search(self, query, *, limit=5):
            return evidence()[:limit]

    with adapter("Dry running [S2]. Inlet [S1]. Again [S2].") as (generator, _):
        result = RagAnswerService(Retriever(), generator).answer("pressure")
        assert result.answer == "Dry running [S1]. Inlet [S2]. Again [S1]."
        assert [citation.chunk_id for citation in result.citations] == ["chunk-2", "chunk-1"]


@pytest.mark.parametrize(
    "finish", ["length", "content_filter", "tool_calls", None, "insufficient_system_resource"]
)
def test_partial_outputs_are_not_reported_as_complete(finish):
    with adapter("Incomplete [S1]", finish=finish) as (generator, _):
        with pytest.raises(ModelServiceError, match="incomplete"):
            generator.generate("pressure", evidence())


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": None},
        {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "text [S1]", "tool_calls": [{"id": "bad"}]},
                }
            ]
        },
    ],
)
def test_malformed_response_is_a_safe_service_error(body):
    with adapter(body=body) as (generator, _):
        with pytest.raises(ModelServiceError):
            generator.generate("pressure", evidence())


@pytest.mark.parametrize("status", [401, 402, 429, 500, "timeout"])
def test_provider_failure_has_no_retry_or_sensitive_body(status):
    with adapter(status=status, body={"error": {"message": "private-provider-body"}}) as (
        generator,
        calls,
    ):
        with pytest.raises(ModelServiceError) as error:
            generator.generate("private-query", evidence())
        assert "private" not in str(error.value)
        assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        {"api_key": ""},
        {"model": " "},
        {"base_url": ""},
        {"max_tokens": 0},
        {"max_tokens": 4097},
        {"timeout_seconds": 0},
    ],
)
def test_invalid_constructor_configuration(override):
    values = dict(api_key="test", model="test", base_url="https://example.test")
    with pytest.raises(ValueError):
        ChatCompletionsAnswerGenerator(**(values | override))


def test_factory_selects_chat_mode_and_disables_sdk_retries(monkeypatch):
    import backend.app.infrastructure.chat_answer_generator as module

    settings = Settings(
        _env_file=None,
        answer_generator="chat_completions",
        llm_api_key="test",
        llm_model="test-model",
        llm_base_url="https://api.deepseek.com",
        chat_disable_thinking=True,
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    constructor_calls = []
    monkeypatch.setattr(module, "OpenAI", lambda **kwargs: constructor_calls.append(kwargs))
    assert isinstance(dependencies.get_answer_generator(), ChatCompletionsAnswerGenerator)
    assert constructor_calls[0]["max_retries"] == 0
    assert constructor_calls[0]["base_url"] == "https://api.deepseek.com"


@pytest.mark.parametrize("key,model", [("", "model"), ("key", "")])
def test_chat_mode_requires_explicit_credentials(monkeypatch, key, model):
    settings = Settings(
        _env_file=None, answer_generator="chat_completions", llm_api_key=key, llm_model=model
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    with pytest.raises(ValueError, match="LLM_API_KEY and LLM_MODEL"):
        dependencies.get_answer_generator()


@pytest.mark.parametrize(
    "content,finish,expected",
    [
        ("Inspect inlet [S1].", "stop", 200),
        ("Bad [S999]", "stop", 502),
        ("Cut off [S1]", "length", 503),
    ],
)
def test_chat_adapter_through_real_answer_route(content, finish, expected, caplog):
    with adapter(content, finish=finish) as (generator, calls):
        app = create_app()
        # get_rag_answer_service calls this factory directly, not via Depends.
        app.dependency_overrides[dependencies.get_rag_answer_service] = lambda: RagAnswerService(
            dependencies.build_keyword_retriever([item.chunk for item in evidence()]), generator
        )
        response = TestClient(app).post("/api/v1/answers", json={"query": "pressure"})
        assert response.status_code == expected
        assert len(calls) == 1
        assert "test-only-key" not in response.text + caplog.text
        if expected == 200:
            assert response.json()["generation_method"] == "chat-completions:test-model"
        else:
            assert response.json()["request_id"]


def test_config_bounds_output_budget():
    with pytest.raises(ValueError):
        Settings(_env_file=None, chat_max_tokens=0)
    assert get_settings().answer_generator == "extractive"
