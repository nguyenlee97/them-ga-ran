"""
Ensemble orchestrator — graceful-degrading layers:
  L1 assoc_rules  →  L2 context_pop (fill)  →  [L3 embeddings]  →
  merge/dedupe  →  L4 personalize (logged-in)  →  L5 llm_rerank + VN copy.
Plus a distinct combo trade-up ("Nâng cấp lên Combo") surfaced separately.

If OpenAI/Qdrant are down, L1+L2 still return solid recommendations.
"""
from app.db import get_db
from app.config import config
from app.pipeline.assoc_rules import candidates_from_rules
from app.pipeline.context_pop import candidates_from_context
from app.pipeline import embeddings
from app.pipeline.personalize import rerank_personal
from app.pipeline.llm_rerank import llm_rerank
from app.pipeline.combo_upsell import best_combo_upsell

import time as _time
_PROD_CACHE = {"data": None, "ts": 0.0}
_PROD_TTL = 120.0  # seconds — menu rarely changes; avoids re-fetching every request


def _product_index(force=False):
    now = _time.time()
    if not force and _PROD_CACHE["data"] is not None and (now - _PROD_CACHE["ts"]) < _PROD_TTL:
        return _PROD_CACHE["data"]
    db = get_db()
    prods = list(db.products.find({"available": True}))
    idx = {p["sku"]: p for p in prods}
    _PROD_CACHE["data"] = idx
    _PROD_CACHE["ts"] = now
    return idx


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

    # Complement categories already covered by the cart (a combo bundles a
    # drink + side). Closes the L1 gap where e.g. a cart with a Pepsi could
    # still get 7Up suggested — rules only exclude exact SKUs, not categories.
    covered = set()
    for s in cart_skus:
        p = prod_idx.get(s) or {}
        t = p.get("tags") or []
        if p.get("isCombo"):
            covered.update(("drink", "side"))
        for k in ("drink", "side", "dessert"):
            if k in t:
                covered.add(k)

    strategies = []
    candidates = []

    # L1 — association rules
    l1 = candidates_from_rules(cart_skus, ctx, limit=20)
    if l1:
        strategies.append("assoc_rule")
        candidates.extend(l1)

    # L2 — complete-the-meal fallback / fill
    l2 = candidates_from_context(cart_skus, cart_tags, ctx, limit=20)
    if l2:
        strategies.append("context_pop")
        candidates.extend(l2)

    # L3 — optional vector similarity (off unless RECO_USE_EMBEDDINGS=true)
    if config.USE_EMBEDDINGS and embeddings.available() and cart_skus:
        seed = ", ".join(name_of(s) for s in list(cart_skus)[:3])
        l3 = embeddings.similar_skus(seed, exclude=cart_skus, limit=8)
        if l3:
            strategies.append("embedding")
            candidates.extend(l3)

    # Rank data-driven association rules above the generic fallback.
    PRIO = {"assoc_rule": 2, "embedding": 1, "context_pop": 0}
    prio_of = lambda c: PRIO.get(str(c.get("strategy", "")).split("+")[0], 0)

    # Diversify key: complement category of a candidate.
    def _cat(sku):
        t = prod_idx[sku].get("tags") or []
        for k in ("drink", "side", "dessert"):
            if k in t:
                return k
        return "other"

    # merge/dedupe: keep the HIGHER-PRIORITY layer per item, then higher score.
    # Never recommend a combo as an add-on; never re-suggest a cart item;
    # never suggest a complement category the cart already covers.
    merged = {}
    for c in candidates:
        sku = c["sku"]
        prod = prod_idx.get(sku)
        if sku in cart_skus or not prod or prod.get("isCombo"):
            continue
        if _cat(sku) in covered:
            continue
        cur = merged.get(sku)
        if cur is None or (prio_of(c), c.get("score", 0)) > (prio_of(cur), cur.get("score", 0)):
            merged[sku] = c

    # Active-promo nudge (all users): promoted/new items get a small boost.
    if config.PROMO_BOOST:
        for c in merged.values():
            p = prod_idx.get(c["sku"]) or {}
            if p.get("promoIds") or "new" in (p.get("tags") or []):
                c["score"] = c.get("score", 0) + config.PROMO_BOOST

    # Calibrate scores across layers: bake the layer priority into the score
    # once (assoc_rule +1.0, embedding +0.5, context_pop +0) so every
    # downstream sort — personalization, diversity — compares on ONE scale.
    # Personal-favorite boosts (≤ ~0.6) can still lift an item within reach,
    # but a strong mined rule isn't dethroned by a generic fallback.
    for c in merged.values():
        c["score"] = c.get("score", 0) + prio_of(c) * 0.5
    ranked = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)

    # L4 — personalize (logged-in only): recency-weighted affinity blended
    # with context (time/dine/store), category backoff, cold-start scaling.
    # Runs BEFORE the diversity pass — diversity is the final arbiter, so a
    # member with strong drink affinity still gets one drink + side + dessert,
    # with their favorites winning WITHIN each category.
    personalization = None
    if ctx.get("userId"):
        ranked, personalization = rerank_personal(ranked, ctx, prod_idx)
        if personalization.get("used"):
            strategies.append(
                "personalize_cold_start" if personalization.get("cold_start") else "personalize"
            )

    # Diversify: prefer one per complement category (drink / side / dessert).
    seen_cat, primary, rest = {}, [], []
    for c in ranked:
        cat = _cat(c["sku"])
        if seen_cat.get(cat, 0) < 1:
            seen_cat[cat] = 1
            primary.append(c)
        else:
            rest.append(c)
    # Primary picks (one per category) ordered by personalized score.
    primary.sort(key=lambda x: x.get("score", 0), reverse=True)
    pool = (primary + rest)[:12]

    # L5 — LLM rerank + VN copy (guardrailed)
    picks, used_llm = llm_rerank(pool, ctx, name_of, limit=limit)
    if used_llm:
        strategies.append("llm_rerank")

    # shape complement output
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

    # Combo trade-up (distinct recommendation type)
    combo_up = best_combo_upsell(cart, prod_idx)
    if combo_up:
        strategies.append("combo_upsell")

    explain = {"strategies_used": strategies, "candidate_pool": len(pool)}
    if personalization is not None:
        explain["personalization"] = personalization

    return {
        "slot": slot,
        "recommendations": recs,
        "comboUpsell": combo_up,
        "explain": explain,
    }
