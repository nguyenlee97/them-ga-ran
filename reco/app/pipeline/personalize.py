"""
L4 — Personalization re-rank (logged-in only).

Boosts candidates the user has bought before (item-based affinity from their
transaction history). Skipped entirely for anonymous sessions. Cheap and
effective; a full implicit-ALS model is the documented upgrade path.
"""
from collections import Counter
from bson import ObjectId
from app.db import get_db


def user_affinity(user_id):
    """Return {sku: normalized_freq} from the user's past transactions."""
    if not user_id:
        return {}
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except Exception:
        return {}
    counts = Counter()
    for tx in db.transactions.find({"userId": oid}, {"lines.sku": 1}):
        for l in tx.get("lines", []):
            counts[l["sku"]] += 1
    if not counts:
        return {}
    mx = max(counts.values())
    return {sku: c / mx for sku, c in counts.items()}


def rerank_personal(candidates, user_id, boost=0.5):
    aff = user_affinity(user_id)
    if not aff:
        return candidates, False
    for c in candidates:
        b = aff.get(c["sku"], 0.0)
        if b > 0:
            c["score"] = c.get("score", 0.0) + boost * b
            c["reason"] = "Món bạn hay gọi — " + c.get("reason", "")
            c["personalized"] = True
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return candidates, True
