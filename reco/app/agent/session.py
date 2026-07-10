"""MongoDB-backed chat session memory (P4)."""
from app.db import get_db


def load_session(session_id):
    db = get_db()
    s = db.sessions.find_one({"sessionId": session_id})
    if not s:
        s = {"sessionId": session_id, "messages": [], "state": {}, "cartId": None}
        db.sessions.insert_one(s)
    return s


def save_session(session_id, messages, state=None, cart_id=None):
    db = get_db()
    upd = {"messages": messages}
    if state is not None:
        upd["state"] = state
    if cart_id is not None:
        upd["cartId"] = cart_id
    db.sessions.update_one({"sessionId": session_id}, {"$set": upd}, upsert=True)
