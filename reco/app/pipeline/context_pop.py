"""
L2 — Contextual popularity / complete-the-meal.

Robust fallback that needs no ML: if the cart is missing a category (drink /
side / dessert), suggest the contextually-appropriate bestsellers. Also covers
cold items via category-level logic. Directly answers "static menu ignores
context".
"""
from app.db import get_db


def _tag(p, t):
    return t in (p.get("tags") or [])


def candidates_from_context(cart_skus, cart_tags, ctx, limit=20):
    db = get_db()
    products = list(db.products.find({"available": True}))
    by_sku = {p["sku"]: p for p in products}

    # A combo in the cart already bundles a drink + side, so treat those as covered.
    has_combo = any((by_sku.get(s, {}) or {}).get("isCombo") for s in cart_skus)
    has_drink = has_combo or any("drink" in (by_sku.get(s, {}).get("tags") or []) for s in cart_skus)
    has_side = has_combo or any("side" in (by_sku.get(s, {}).get("tags") or []) for s in cart_skus)
    has_dessert = any("dessert" in (by_sku.get(s, {}).get("tags") or []) for s in cart_skus)
    tod = ctx.get("timeOfDay")

    wanted = []
    if not has_drink:
        wanted.append(("drink", "Thêm nước uống cho trọn bữa", 1.5))
    if not has_side:
        wanted.append(("side", "Gọi thêm món ăn kèm nhé", 1.2))
    if not has_dessert and tod in ("afternoon", "dinner", "late"):
        wanted.append(("dessert", "Tráng miệng ngọt ngào?", 1.0))

    out = []
    for tag, reason, base in wanted:
        # Atomic complements only — never suggest a whole combo as a "drink"/"side".
        pool = [p for p in products
                if _tag(p, tag) and not p.get("isCombo") and p["sku"] not in cart_skus]
        # a "drink" suggestion must be a real drink, not e.g. a chicken item tagged for other reasons
        if tag == "drink":
            pool = [p for p in pool if "chicken" not in (p.get("tags") or [])]
        # bestsellers first, then larger size (natural upsell)
        pool.sort(key=lambda p: (("bestseller" in (p.get("tags") or [])), -p["price"]), reverse=True)
        for i, p in enumerate(pool[:4]):
            out.append({
                "sku": p["sku"],
                "score": base - i * 0.1,
                "reason": reason,
                "strategy": "context_pop",
            })
    return out[:limit]
