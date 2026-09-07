from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.answer_generators import NO_EVIDENCE_ANSWER
from backend.app.infrastructure.openai_answer_generator import (
    GENERATOR_INSTRUCTIONS,
    OpenAIResponsesAnswerGenerator,
)
from backend.app.ports.answering import AnswerGenerator
from backend.app.ports.retrieval import SearchResult


@dataclass
class FakeResponse:
    output_text: str


class FakeResponsesResource:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, str]] = []

    def create(
        self,
        *,
        model: str,
        instructions: str,
        input: str,
    ) -> FakeResponse:
        self.calls.append(
            {
                "model": model,
                "instructions": instructions,
                "input": input,
            }
        )
        return FakeResponse(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponsesResource(output_text)


def make_evidence() -> Sequence[SearchResult]:
    return [
        SearchResult(
            chunk=Chunk(
                chunk_id="chunk-pressure",
                document_id="manual-001",
                text="Inspect the suction line for blockage.",
                chunk_index=0,
                source="pump_manual.pdf",
                page_number=7,
            ),
            score=0.9,
        ),
        SearchResult(
            chunk=Chunk(
                chunk_id="chunk-seal",
                document_id="manual-001",
                text="Isolate power before replacing the mechanical seal.",
                chunk_index=1,
                source="pump_manual.pdf",
                page_number=9,
            ),
            score=0.8,
        ),
    ]


def build_generator(output_text: str) -> tuple[OpenAIResponsesAnswerGenerator, FakeClient]:
    client = FakeClient(output_text)
    generator = OpenAIResponsesAnswerGenerator(
        api_key="",
        model="test-model",
        client=client,
    )
    return generator, client


def test_openai_generator_matches_answer_generator_port() -> None:
    generator, _ = build_generator("Use the suction line procedure. [S1]")

    assert isinstance(generator, AnswerGenerator)


def test_openai_generator_builds_grounded_request_and_maps_citations() -> None:
    generator, client = build_generator(
        "Isolate power first. [S2] Then inspect the suction line. [S1] [S2]"
    )

    draft = generator.generate(
        "How should I inspect the pump?",
        make_evidence(),
    )

    assert draft.cited_chunk_ids == ["chunk-seal", "chunk-pressure"]
    assert draft.answer == "Isolate power first. [S1] Then inspect the suction line. [S2] [S1]"
    assert draft.generation_method == "openai-responses:test-model"
    assert len(client.responses.calls) == 1

    request = client.responses.calls[0]
    assert request["model"] == "test-model"
    assert request["instructions"] == GENERATOR_INSTRUCTIONS
    assert "Question:\nHow should I inspect the pump?" in request["input"]
    assert "[S1] source=pump_manual.pdf; page=7" in request["input"]
    assert "[S2] source=pump_manual.pdf; page=9" in request["input"]


@pytest.mark.parametrize(
    "output_text",
    [
        "",
        "This answer has no citation.",
        NO_EVIDENCE_ANSWER,
    ],
)
def test_openai_generator_falls_back_for_unverifiable_output(
    output_text: str,
) -> None:
    generator, _ = build_generator(output_text)

    draft = generator.generate("pump pressure", make_evidence())

    assert draft.answer == NO_EVIDENCE_ANSWER
    assert draft.cited_chunk_ids == []


def test_openai_generator_skips_api_call_without_evidence() -> None:
    generator, client = build_generator("Would otherwise answer. [S1]")

    draft = generator.generate("pump pressure", [])

    assert draft.answer == NO_EVIDENCE_ANSWER
    assert client.responses.calls == []


@pytest.mark.parametrize("marker", ["[S0]", "[S3]"])
def test_openai_generator_rejects_invalid_source_marker(marker: str) -> None:
    generator, _ = build_generator(f"Unsupported citation {marker}")

    with pytest.raises(ValueError, match="source marker"):
        generator.generate("pump pressure", make_evidence())


@pytest.mark.parametrize(
    ("api_key", "model", "base_url", "timeout", "message"),
    [
        ("", "model", "https://api.openai.com/v1", 30.0, "api_key"),
        ("key", "", "https://api.openai.com/v1", 30.0, "model"),
        ("key", "model", "", 30.0, "base_url"),
        ("key", "model", "https://api.openai.com/v1", 0.0, "timeout_seconds"),
    ],
)
def test_openai_generator_rejects_invalid_configuration(
    api_key: str,
    model: str,
    base_url: str,
    timeout: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        OpenAIResponsesAnswerGenerator(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout,
        )


def test_openai_generator_rejects_blank_query() -> None:
    generator, _ = build_generator("Answer. [S1]")

    with pytest.raises(ValueError, match="query"):
        generator.generate("  ", make_evidence())


@pytest.mark.parametrize(
    ("output", "expected_answer", "expected_ids"),
    [
        ("Isolate power. [S2]", "Isolate power. [S1]", ["chunk-seal"]),
        (
            "Seal. [S2] Pressure. [S1] Seal again. [S2]",
            "Seal. [S1] Pressure. [S2] Seal again. [S1]",
            ["chunk-seal", "chunk-pressure"],
        ),
    ],
)
def test_model_citations_remain_consistent_through_rag_service(
    output: str, expected_answer: str, expected_ids: list[str]
) -> None:
    from backend.app.services.rag_answering import RagAnswerService

    class EvidenceRetriever:
        def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
            return list(make_evidence())[:limit]

    generator, _ = build_generator(output)
    result = RagAnswerService(EvidenceRetriever(), generator).answer("pump pressure")
    assert result.answer == expected_answer
    assert [citation.chunk_id for citation in result.citations] == expected_ids
    assert [citation.citation_id for citation in result.citations] == [
        f"S{index}" for index in range(1, len(expected_ids) + 1)
    ]


def test_model_transport_errors_are_converted_without_provider_body() -> None:
    import httpx
    from openai import APIConnectionError

    from backend.app.core.errors import ModelServiceError

    class UnavailableResponses:
        def create(self, **kwargs: str) -> FakeResponse:
            raise APIConnectionError(
                message="sensitive-provider-body",
                request=httpx.Request("POST", "https://example.com"),
            )

    client = FakeClient("")
    client.responses = UnavailableResponses()
    generator = OpenAIResponsesAnswerGenerator(api_key="", model="fake", client=client)
    with pytest.raises(ModelServiceError, match="temporarily unavailable") as error:
        generator.generate("pump", make_evidence())
    assert "sensitive-provider-body" not in str(error.value)
