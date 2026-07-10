"""
L1 — Market-basket association rules (the backbone).

Reads precomputed rules from the `assocrules` collection (written by
mine_rules.py) and serves complements for the current cart. Fully explainable,
sub-5ms, no cold-start for popular items.
"""
from app.db import get_db


def candidates_from_rules(cart_skus, ctx, limit=20):
    if not cart_skus:
        return []
    db = get_db()
    tod = ctx.get("timeOfDay") or "any"
    dine = ctx.get("dineMode") or "any"

    # Rules whose antecedent is a SUBSET of the cart, matching context (or 'any').
    query = {
        "antecedent": {"$not": {"$elemMatch": {"$nin": list(cart_skus)}}, "$ne": []},
        "consequent": {"$nin": list(cart_skus)},
        "$and": [
            {"$or": [{"context.timeOfDay": tod}, {"context.timeOfDay": "any"}]},
            {"$or": [{"context.dineMode": dine}, {"context.dineMode": "any"}]},
        ],
    }
    rows = list(db.assocrules.find(query).limit(300))

    # Keep the best rule per consequent; score = lift * confidence.
    best = {}
    for r in rows:
        sku = r["consequent"]
        score = (r.get("lift") or 1.0) * (r.get("confidence") or 0.0)
        specificity = len(r.get("antecedent") or [])  # prefer specific rules
        cand = {
            "sku": sku,
            "score": score,
            "confidence": r.get("confidence"),
            "lift": r.get("lift"),
            "strategy": "assoc_rule",
            "_spec": specificity,
        }
        if sku not in best or (score, specificity) > (best[sku]["score"], best[sku]["_spec"]):
            best[sku] = cand

    out = sorted(best.values(), key=lambda x: (x["score"], x["_spec"]), reverse=True)
    for c in out:
        conf = c.get("confidence")
        c["reason"] = (
            f"Đi kèm phổ biến — {round((conf or 0) * 100)}% khách mua cùng"
            if conf else "Thường được mua cùng"
        )
        c.pop("_spec", None)
    return out[:limit]
