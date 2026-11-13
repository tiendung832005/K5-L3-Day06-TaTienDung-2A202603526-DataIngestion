"""Choose a real embedding provider (API or local) and implement this contract."""
from typing import Protocol
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, question: str) -> list[float]:
        ...


class MyEmbedder:
    """Real local SentenceTransformers embedder; never falls back to mock vectors."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        resolved_name = (model_name or "").strip() or DEFAULT_MODEL
        self.model_name = resolved_name
        self._model = SentenceTransformer(resolved_name)
        dim = self._model.get_embedding_dimension()
        if not dim or dim <= 0:
            dim = len(self._model.encode(["dimension probe"], show_progress_bar=False)[0])
        self.dimensions: int = int(dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [v.tolist() for v in vecs]

    def embed_query(self, question: str) -> list[float]:
        if not question or not question.strip():
            raise ValueError("Query question cannot be empty")
        vec = self._model.encode(
            [question.strip()],
            show_progress_bar=False,
            normalize_embeddings=True,
        )[0]
        return vec.tolist()
