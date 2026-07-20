from __future__ import annotations

"""RerankClient adapter (Section 11.6 — the poster's "Context Ranking (Cohere Rerank)" step).

Context assembly retrieves broadly by source type; reranking keeps only what's actually
relevant to the current question/persona/scope. Same house pattern as the other adapters.

  RERANK_CLIENT_MODE=local   -> LocalRerankClient: cosine similarity between the question and
                               each candidate via the existing EmbeddingClient (free, no new
                               vendor — the "cosine-similarity as a rerank proxy" 11.6 allows).
  RERANK_CLIENT_MODE=cohere  -> CohereRerankClient: the real Cohere Rerank API (COHERE_API_KEY).

Heavy/SDK imports stay inside the implementations.
"""

import math
from typing import Protocol, TypedDict

from app.config.settings import get_settings


class RerankResult(TypedDict):
    index: int
    score: float


class RerankClient(Protocol):
    def rerank(self, query: str, documents: list[str], top_k: int | None = None) -> list[RerankResult]: ...

    def describe(self) -> dict: ...


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class LocalRerankClient:
    """Embedding-cosine rerank proxy — reuses the existing EmbeddingClient (all-MiniLM by
    default), so it's free and needs no new model download beyond what RAG already loads."""

    def rerank(self, query: str, documents: list[str], top_k: int | None = None) -> list[RerankResult]:
        if not documents:
            return []
        from app.llm.embedding_client import get_embedding_client

        emb = get_embedding_client()
        qv = emb.embed(query)
        dvs = emb.embed_many(documents)
        scored = [{"index": i, "score": round(_cosine(qv, dv), 4)} for i, dv in enumerate(dvs)]
        scored.sort(key=lambda r: -r["score"])
        return scored[: top_k or len(scored)]

    def describe(self) -> dict:
        return {"mode": "local", "backend": "embedding-cosine-proxy"}


class CohereRerankClient:
    """Real Cohere Rerank — the tool the poster names. Lazy SDK import; needs COHERE_API_KEY."""

    def __init__(self) -> None:
        settings = get_settings()
        key = getattr(settings, "cohere_api_key", None)
        if not key:
            raise RuntimeError("RERANK_CLIENT_MODE=cohere requires COHERE_API_KEY in .env")
        import cohere  # noqa: F401 — imported here so nothing else depends on the SDK

        self._client = cohere.Client(key)
        self._model = getattr(settings, "cohere_rerank_model", "rerank-english-v3.0")

    def rerank(self, query: str, documents: list[str], top_k: int | None = None) -> list[RerankResult]:
        if not documents:
            return []
        resp = self._client.rerank(query=query, documents=documents,
                                   top_n=top_k or len(documents), model=self._model)
        return [{"index": r.index, "score": round(float(r.relevance_score), 4)} for r in resp.results]

    def describe(self) -> dict:
        return {"mode": "cohere", "model": self._model}


_rerank_client: RerankClient | None = None


def get_rerank_client() -> RerankClient:
    global _rerank_client
    if _rerank_client is None:
        mode = getattr(get_settings(), "rerank_client_mode", "local").lower()
        if mode == "local":
            _rerank_client = LocalRerankClient()
        elif mode == "cohere":
            _rerank_client = CohereRerankClient()
        else:
            raise ValueError(f"Unknown RERANK_CLIENT_MODE '{mode}' (expected local|cohere)")
    return _rerank_client


def reset_rerank_client() -> None:
    global _rerank_client
    _rerank_client = None
