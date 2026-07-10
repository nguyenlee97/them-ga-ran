from pymongo import MongoClient
from app.config import config

_client = None


def get_db():
    """Shared pymongo database handle (DB name comes from the URI)."""
    global _client
    if _client is None:
        _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000)
    return _client.get_default_database()
