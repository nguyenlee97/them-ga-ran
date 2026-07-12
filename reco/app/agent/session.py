"""MongoDB-backed chat session memory (P4)."""
from datetime import datetime, timezone

from app.db import get_db


def load_session(session_id):
    db = get_db()
    s = db.sessions.find_one({"sessionId": session_id})
    if not s:
        s = {"sessionId": session_id, "messages": [], "state": {}, "cartId": None}
        db.sessions.insert_one(s)
    return s


def save_session(session_id, messages, state=None, cart_id=None,
                 conversation_started_at=None):
    db = get_db()
    now = datetime.now(timezone.utc)
    upd = {"messages": messages, "lastActivityAt": now}
    if state is not None:
        upd["state"] = state
    if cart_id is not None:
        upd["cartId"] = cart_id
    if conversation_started_at is not None:
        upd["conversationStartedAt"] = conversation_started_at
    db.sessions.update_one(
        {"sessionId": session_id},
        {"$set": upd, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
