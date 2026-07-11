"""
L4 — Personalization re-rank (logged-in only), v2.

Recency-weighted item affinity from the member's transaction history, blended
with the current context (time of day / dine mode / store), with a
category-level backoff for items they've never bought. Cold-start aware:
with fewer than RECO_MIN_HISTORY transactions the boost is scaled down
proportionally, so brand-new members degrade gracefully to the anonymous
ensemble instead of getting noisy nudges.

Because placed orders are appended to `transactions` (the order→transactions
feedback loop), an order placed a minute ago already carries near-full recency
weight — the system visibly learns during a live demo.
"""
from datetime import datetime
from bson import ObjectId
from app.db import get_db
from app.config import config

# Context blend: history that matches the CURRENT context counts extra.
TOD_MULT = 1.5     # same time-of-day
DINE_MULT = 1.2    # same dine mode
STORE_MULT = 1.25  # same store


def _taste_key(prod, fallback=None):
    """Complement-tag taste key (drink/side/dessert). The VN `category` string
    is too coarse — KFC puts drinks AND desserts in one category ("Thức Uống &
    Tráng Miệng"), which made dessert-lovers look like drink-lovers."""
    t = (prod or {}).get("tags") or []
    for k in ("drink", "side", "dessert", "chicken", "burger"):
        if k in t:
            return k
    return (prod or {}).get("category") or fallback


def _history(user_id):
    if not user_id:
        return []
    try:
        oid = ObjectId(user_id)
    except Exception:
        return []
    db = get_db()
    return list(db.transactions.find(
        {"userId": oid},
        {"ts": 1, "timeOfDay": 1, "dineMode": 1, "storeId": 1,
         "lines.sku": 1, "lines.qty": 1, "lines.category": 1},
    ))


def affinity(user_id, ctx, prod_idx=None):
    """
    Returns {"items": {sku: 0..1}, "cats": {taste_key: 0..1}, "n": tx_count}
    or None when the user has no history at all.
    Weight per transaction = recency decay x context match multipliers.
    """
    prod_idx = prod_idx or {}
    txs = _history(user_id)
    if not txs:
        return None

    now = datetime.utcnow()
    half_life = max(1.0, config.AFFINITY_HALF_LIFE_DAYS)
    ctx_tod = ctx.get("timeOfDay")
    ctx_dine = ctx.get("dineMode")
    ctx_store = str(ctx.get("storeId") or "")

    item_scores, cat_scores = {}, {}
    for tx in txs:
        ts = tx.get("ts")
        if isinstance(ts, datetime):
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
        else:
            age_days = half_life  # unknown age → neutral-ish weight

        w = 0.5 ** (age_days / half_life)
        if ctx_tod and tx.get("timeOfDay") == ctx_tod:
            w *= TOD_MULT
        if ctx_dine and tx.get("dineMode") == ctx_dine:
            w *= DINE_MULT
        if ctx_store and str(tx.get("storeId") or "") == ctx_store:
            w *= STORE_MULT

        for line in tx.get("lines", []):
            sku = line.get("sku")
            if not sku:
                continue
            qty = line.get("qty") or 1
            item_scores[sku] = item_scores.get(sku, 0.0) + w * qty
            cat = _taste_key(prod_idx.get(sku), fallback=line.get("category"))
            if cat:
                cat_scores[cat] = cat_scores.get(cat, 0.0) + w * qty

    def _norm(d):
        mx = max(d.values()) if d else 0.0
        return {k: v / mx for k, v in d.items()} if mx > 0 else {}

    return {"items": _norm(item_scores), "cats": _norm(cat_scores), "n": len(txs)}


def rerank_personal(candidates, ctx, prod_idx):
    """
    Boost candidates by the member's affinity. Returns (candidates, info):
    info = {"used": bool, "cold_start": bool, "n_history": int}.
    """
    aff = affinity(ctx.get("userId"), ctx, prod_idx)
    if aff is None:
        return candidates, {"used": False, "cold_start": True, "n_history": 0}

    n = aff["n"]
    cold = n < config.MIN_HISTORY
    # Cold start: scale the whole personal signal down proportionally.
    scale = min(1.0, n / max(1, config.MIN_HISTORY))

    for c in candidates:
        sku = c["sku"]
        prod = prod_idx.get(sku) or {}
        exact = aff["items"].get(sku, 0.0)
        cat = aff["cats"].get(_taste_key(prod), 0.0)

        if exact > 0:
            c["score"] = c.get("score", 0.0) + scale * config.PERSONAL_BOOST * exact
            if exact >= 0.35:
                c["reason"] = "Món bạn hay gọi — " + c.get("reason", "")
            c["personalized"] = True
        elif cat > 0:
            # Never bought this item, but it's squarely in their taste.
            c["score"] = c.get("score", 0.0) + scale * config.CATEGORY_BOOST * cat
            if cat >= 0.5:
                c["reason"] = "Hợp gu bạn — " + c.get("reason", "")
            c["personalized"] = True

    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return candidates, {"used": True, "cold_start": cold, "n_history": n}
