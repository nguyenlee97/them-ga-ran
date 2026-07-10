"""
Ensemble orchestrator — graceful-degrading layers:
  L1 assoc_rules  →  L2 context_pop (fill)  →  [L3 embeddings]  →
  merge/dedupe  →  L4 personalize (logged-in)  →  L5 llm_rerank + VN copy.

If OpenAI/Qdrant are down, L1+L2 still return solid recommendations.
"""
from app.db import get_db
from app.pipeline.assoc_rules import candidates_from_rules
from app.pipeline.context_pop import candidates_from_context
from app.pipeline import embeddings
from app.pipeline.personalize import rerank_personal
from app.pipeline.llm_rerank import llm_rerank


def _product_index():
    db = get_db()
    prods = list(db.products.find({"available": True}))
    return {p["sku"]: p for p in prods}


def recommend(slot, ctx, limit=3):
    prod_idx = _product_index()
    name_of = lambda sku: (prod_idx.get(sku) or {}).get("name_vi", sku)

    cart = ctx.get("cart") or []
    cart_skus = set(x.get("sku") for x in cart if x.get("sku"))
    # If only productIds were sent, map them to skus.
    if cart and not cart_skus:
        by_id = {str(p["_id"]): p for p in prod_idx.values()}
        cart_skus = set(by_id[x["productId"]]["sku"] for x in cart
                        if x.get("productId") in by_id)
    cart_tags = set()
    for s in cart_skus:
        cart_tags.update((prod_idx.get(s) or {}).get("tags") or [])

    strategies = []
    candidates = []

    # L1
    l1 = candidates_from_rules(cart_skus, ctx, limit=20)
    if l1:
        strategies.append("assoc_rule")
        candidates.extend(l1)

    # L2 — always add complements, used as fill / when L1 thin
    l2 = candidates_from_context(cart_skus, cart_tags, ctx, limit=20)
    if l2:
        strategies.append("context_pop")
        candidates.extend(l2)

    # L3 — optional vector similarity to broaden candidate pool
    if embeddings.available() and cart_skus:
        seed = ", ".join(name_of(s) for s in list(cart_skus)[:3])
        l3 = embeddings.similar_skus(seed, exclude=cart_skus, limit=8)
        if l3:
            strategies.append("embedding")
            candidates.extend(l3)

    # merge/dedupe keeping best score per sku
    merged = {}
    for c in candidates:
        sku = c["sku"]
        if sku in cart_skus or sku not in prod_idx:
            continue
        if sku not in merged or c.get("score", 0) > merged[sku].get("score", 0):
            merged[sku] = c
    pool = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)[:12]

    # L4 — personalize (logged-in only)
    if ctx.get("userId"):
        pool, used = rerank_personal(pool, ctx["userId"])
        if used:
            strategies.append("personalize")

    # L5 — LLM rerank + VN copy (guardrailed)
    picks, used_llm = llm_rerank(pool, ctx, name_of, limit=limit)
    if used_llm:
        strategies.append("llm_rerank")

    # shape output + attach product fields
    recs = []
    for c in picks:
        p = prod_idx.get(c["sku"], {})
        recs.append({
            "sku": c["sku"],
            "productId": str(p.get("_id", "")),
            "name": p.get("name_vi", c["sku"]),
            "price": p.get("price"),
            "imageUrl": p.get("imageUrl"),
            "reason": c.get("reason", ""),
            "copy": c.get("copy", ""),
            "strategy": c.get("strategy", ""),
            "score": round(float(c.get("score", 0)), 4),
        })

    return {
        "slot": slot,
        "recommendations": recs,
        "explain": {"strategies_used": strategies, "candidate_pool": len(pool)},
    }
