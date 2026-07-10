"""
L3 — Item embeddings + vector similarity (optional).

Reuses the Claw-a-thon approach: fastembed (CPU, no torch) → Qdrant. Powers
menu semantic search and complementary-item retrieval. Guarded: if fastembed or
Qdrant is unavailable, callers simply skip this layer.
"""
from app.config import config

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=config.RAG_DENSE_MODEL)
    return _model


def available():
    try:
        from qdrant_client import QdrantClient  # noqa
        return True
    except Exception:
        return False


def embed(texts):
    return [v.tolist() for v in _get_model().embed(texts)]


def similar_skus(query_text, exclude=(), limit=10):
    """Best-effort vector search; returns [] on any failure."""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=config.QDRANT_URL)
        vec = embed([query_text])[0]
        res = client.query_points(
            config.RAG_COLLECTION, query=vec, limit=limit + len(exclude), with_payload=True
        )
        out = []
        for p in res.points:
            sku = (p.payload or {}).get("sku")
            if sku and sku not in exclude:
                out.append({"sku": sku, "score": float(p.score), "strategy": "embedding",
                            "reason": "Món tương tự bạn có thể thích"})
        return out[:limit]
    except Exception:
        return []
