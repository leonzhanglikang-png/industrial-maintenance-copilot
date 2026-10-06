"""CPU semantic embeddings from a pre-downloaded multilingual ONNX model."""

from collections.abc import Sequence
from math import isfinite
from pathlib import Path

from backend.app.core.errors import ModelConfigurationError, ModelServiceError
from backend.app.ports.retrieval import Embedding

LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REPOSITORY = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
MODEL_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"


class LocalSemanticEmbeddingProvider:
    model = LOCAL_MODEL
    dimension = 384

    def __init__(self, model_path: Path, *, model=None) -> None:
        if model is not None:
            self._model = model
            return
        if not (model_path / "model_optimized.onnx").is_file():
            raise ModelConfigurationError("Download the local semantic model before enabling it")
        try:
            import onnxruntime

            onnxruntime.disable_telemetry_events()
            from fastembed import TextEmbedding
        except ImportError:
            raise ModelConfigurationError(
                "Install the semantic extra to use local embeddings"
            ) from None
        try:
            self._model = TextEmbedding(
                model_name=self.model,
                specific_model_path=str(model_path),
                local_files_only=True,
                threads=2,
                providers=["CPUExecutionProvider"],
                cuda=False,
            )
        except Exception:
            raise ModelServiceError("Local semantic model could not be loaded") from None

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if any(not text.strip() for text in texts):
            raise ValueError("embedding input must not be blank")
        if not texts:
            return []
        try:
            vectors = [
                list(map(float, row)) for row in self._model.embed(list(texts), batch_size=8)
            ]
            if len(vectors) != len(texts) or any(
                len(row) != self.dimension
                or not all(isfinite(value) for value in row)
                or not any(row)
                for row in vectors
            ):
                raise ValueError("invalid local vectors")
            return vectors
        except Exception:
            raise ModelServiceError("Local semantic model could not encode the input") from None
