import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    PORT = int(os.getenv("PORT", "8080"))
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/kfc")
    # Backend base URL — the chat agent calls the same REST surface as the kiosk.
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "") or None

    USE_EMBEDDINGS = os.getenv("RECO_USE_EMBEDDINGS", "false").lower() == "true"
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    RAG_COLLECTION = os.getenv("RAG_COLLECTION", "kfc_menu")
    RAG_DENSE_MODEL = os.getenv(
        "RAG_DENSE_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )

    MIN_SUPPORT = float(os.getenv("MIN_SUPPORT", "0.01"))
    MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.15"))

    # L4 personalization (recency-weighted affinity, context blend, cold-start)
    AFFINITY_HALF_LIFE_DAYS = float(os.getenv("RECO_AFFINITY_HALF_LIFE_DAYS", "30"))
    MIN_HISTORY = int(os.getenv("RECO_MIN_HISTORY", "3"))  # txs below which = cold start
    PERSONAL_BOOST = float(os.getenv("RECO_PERSONAL_BOOST", "0.6"))  # exact-item cap
    CATEGORY_BOOST = float(os.getenv("RECO_CATEGORY_BOOST", "0.2"))  # category backoff cap
    PROMO_BOOST = float(os.getenv("RECO_PROMO_BOOST", "0.15"))  # active-promo nudge (all users)


config = Config()
