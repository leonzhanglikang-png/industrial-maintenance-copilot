"""Bounded, non-streaming Chat Completions for DeepSeek and compatible services."""

from collections.abc import Sequence
from math import isfinite

from openai import APIError, OpenAI

from backend.app.core.errors import ModelServiceError
from backend.app.domain.answers import AnswerDraft
from backend.app.infrastructure.answer_generators import NO_EVIDENCE_ANSWER
from backend.app.infrastructure.openai_answer_generator import (
    GENERATOR_INSTRUCTIONS,
    build_model_input,
    parse_model_answer,
)
from backend.app.ports.retrieval import SearchResult


class ChatCompletionsAnswerGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_tokens: int = 512,
        disable_thinking: bool = False,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key.strip() or not model.strip() or not base_url.strip():
            raise ValueError("api_key, model and base_url must not be blank")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0 or not 1 <= max_tokens <= 4096:
            raise ValueError("timeout must be positive and max_tokens must be between 1 and 4096")
        self._model = model.strip()
        self._max_tokens = max_tokens
        self._disable_thinking = disable_thinking
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            max_retries=0,
        )

    def generate(self, query: str, evidence: Sequence[SearchResult]) -> AnswerDraft:
        if not query.strip():
            raise ValueError("query must not be blank")
        method = f"chat-completions:{self._model}"
        if not evidence:
            return AnswerDraft(answer=NO_EVIDENCE_ANSWER, generation_method=method)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": GENERATOR_INSTRUCTIONS
                        + "\nAnswer concisely in the question's language.",
                    },
                    {"role": "user", "content": build_model_input(query, evidence)},
                ],
                max_tokens=self._max_tokens,
                stream=False,
                extra_body={"thinking": {"type": "disabled"}} if self._disable_thinking else None,
            )
        except APIError:
            raise ModelServiceError("Model service is temporarily unavailable") from None
        try:
            if len(response.choices) != 1:
                raise ValueError("unexpected choice count")
            choice = response.choices[0]
            # Truncated/filtered/tool-call responses must never look like full answers.
            if choice.finish_reason != "stop" or choice.message.tool_calls:
                raise ValueError("incomplete answer")
            content = choice.message.content
            if not isinstance(content, str):
                raise ValueError("missing answer text")
        except (AttributeError, TypeError, ValueError):
            raise ModelServiceError(
                "Model service returned an incomplete or invalid answer"
            ) from None
        return parse_model_answer(content, evidence, method)
