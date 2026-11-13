"""Store and search vectors using ChromaDB Persistent Local Store."""
from pathlib import Path
from typing import Any
import chromadb
from .models import Chunk

ALLOWED_FILTER_KEYS = {
    "section",
    "category",
    "year",
    "version",
    "audience",
    "language",
    "document_type",
    "document_id",
    "source",
}


class PgVectorStore:
    """Persistent Vector Store using ChromaDB."""

    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        self.database_url = database_url
        self.dimensions = dimensions
        persist_dir = Path(__file__).resolve().parent.parent / "chroma_db"
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.persist_path = str(persist_dir)
        self.client = chromadb.PersistentClient(path=self.persist_path)

    def _get_collection(self, strategy: str):
        return self.client.get_or_create_collection(
            name=f"rag_chunks_{strategy}",
            metadata={"hnsw:space": "cosine"},
        )

    def create_schema(self) -> None:
        """Initialize persistent collections for strategies A, B, and C with cosine metric."""
        for strat in ["A", "B", "C"]:
            self._get_collection(strat)

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(vectors)} vectors")
        if not chunks:
            return

        for v in vectors:
            if len(v) != self.dimensions:
                raise ValueError(f"Vector dim {len(v)} != store dim {self.dimensions}")

        col = self._get_collection(strategy)
        doc_ids = sorted({c.document_id for c in chunks})
        keep_ids = {c.chunk_id for c in chunks}

        for doc_id in doc_ids:
            existing = col.get(where={"document_id": doc_id})
            obsolete_ids = [cid for cid in existing.get("ids", []) if cid not in keep_ids]
            if obsolete_ids:
                col.delete(ids=obsolete_ids)

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = []
        for c in chunks:
            clean_meta = {
                "document_id": str(c.document_id),
                "source": str(c.source),
                "page": int(c.page),
                "section": str(c.metadata.get("section", "general")),
                "version": str(c.metadata.get("version", "1.0")),
                "chunk_strategy": str(c.metadata.get("chunk_strategy", strategy)),
            }
            metadatas.append(clean_meta)

        col.upsert(ids=ids, embeddings=vectors, documents=documents, metadatas=metadatas)

    def count_chunks(self, strategy: str) -> int:
        return self._get_collection(strategy).count()

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError(f"Query vector dim {len(query_vector)} != {self.dimensions}")

        col = self._get_collection(strategy)
        where_filter = None
        if filters:
            for k in filters:
                if k not in ALLOWED_FILTER_KEYS:
                    raise ValueError(f"Unsupported filter key: {k}")
            if len(filters) == 1:
                k, v = next(iter(filters.items()))
                where_filter = {k: str(v) if k != "page" else int(v)}
            else:
                where_filter = {"$and": [{k: str(v) if k != "page" else int(v)} for k, v in filters.items()]}

        res = col.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        results: list[dict[str, Any]] = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        for cid, text, meta, dist in zip(ids, docs, metas, dists):
            score = round(1.0 - float(dist), 6)
            results.append(
                {
                    "chunk_id": cid,
                    "document_id": meta.get("document_id"),
                    "source": meta.get("source"),
                    "page": int(meta.get("page", 0)),
                    "text": text,
                    "score": score,
                    "metadata": meta,
                }
            )
        return results
