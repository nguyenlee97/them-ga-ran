import os
from dotenv import load_dotenv

try:
    # Corp networks often do TLS inspection; browsers trust the corporate CA
    # via the OS cert store but Python uses its own bundle and fails with
    # connection errors. truststore makes Python use the OS store like Chrome.
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

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
    PERSONAL_BOOST = float(os.getenv("RECO_PERSONAL_BOOST", "0.8"))  # exact-item cap
    CATEGORY_BOOST = float(os.getenv("RECO_CATEGORY_BOOST", "0.2"))  # category backoff cap
    PROMO_BOOST = float(os.getenv("RECO_PROMO_BOOST", "0.15"))  # active-promo nudge (all users)

    # ── P4 Zalo OA transport ──────────────────────────────────────────────────
    ZALO_APP_ID = os.getenv("ZALO_APP_ID", "")
    ZALO_APP_SECRET = os.getenv("ZALO_APP_SECRET", "")       # app "private key"
    ZALO_OA_SECRET = os.getenv("ZALO_OA_SECRET", "")         # OA secret key (webhook MAC)
    ZALO_ACCESS_TOKEN = os.getenv("ZALO_ACCESS_TOKEN", "")   # seed token (auto-refreshed after)
    ZALO_REFRESH_TOKEN = os.getenv("ZALO_REFRESH_TOKEN", "")
    # Domain-verification meta tag content (method 2). File method: drop the
    # downloaded file into reco/public/ (served automatically).
    ZALO_VERIFY_META = os.getenv("ZALO_VERIFY_META", "")
    # OAuth consent (PKCE) — used by /zalo/oauth/login + /callback to (re)seed tokens.
    ZALO_REDIRECT_URI = os.getenv("ZALO_REDIRECT_URI", "https://pawgrammers.io.vn/zalo/oauth/callback")
    ZALO_OAUTH_PERMISSION_URL = os.getenv("ZALO_OAUTH_PERMISSION_URL", "https://oauth.zaloapp.com/v4/oa/permission")
    # Endpoints (overridable if Zalo revs the API version).
    ZALO_OAUTH_URL = os.getenv("ZALO_OAUTH_URL", "https://oauth.zaloapp.com/v4/oa/access_token")
    ZALO_OA_API_URL = os.getenv("ZALO_OA_API_URL", "https://openapi.zalo.me")
    # Public HTTPS base for QR/pay links Zalo users open from their phone (only
    # the /zalo/ path is exposed via nginx). QR image + pay webhook live here.
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://pawgrammers.io.vn")


config = Config()
