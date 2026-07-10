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


config = Config()
