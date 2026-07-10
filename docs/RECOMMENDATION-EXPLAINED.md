# How the recommendation engine works — business → technical

A layered explanation of the P2 recommendation engine: why it exists, what data
feeds it, the algorithm, and how the pieces are wired together.

---

## 1. Business level — what problem it solves

**Today (the problem):** KFC kiosks show a static menu and a manually-curated
"You may also like" that's identical for everyone and updated monthly. That
misses the single biggest fast-food revenue lever: the **right add-on at the
right moment**. Someone ordering 2 pieces of chicken and no drink is an obvious
drink sale that a static menu never nudges.

**The opportunity:** contextual upsell/cross-sell at the kiosk. KFC's own brief
estimates **10–15% Average Order Value (AOV) uplift** if relevant suggestions
appear at the right point in the ordering journey.

**Where the engine speaks (the "moments"):** the same engine is called at three
high-intent moments, each a different `slot`:
1. **`item_added`** — right after a customer adds an item (highest-converting upsell point): "goes great with…".
2. **`cart`** — on the basket page: "complete your meal".
3. **`checkout`** — one last low-friction add before paying.

**Success metric:** AOV uplift, measured by logging every recommendation shown
vs. accepted (the `events` collection) and comparing basket sizes with/without
accepted suggestions.

**Why it's a good business story:** it replaces manual monthly curation with a
data-driven channel that adapts to time of day, what's already in the basket,
the store, and (for logged-in members) personal history — with **zero extra
staff effort**, across all 250+ restaurants.

---

## 2. Data level — what signals feed it

The engine is designed **anonymous-first** (most kiosk sessions don't log in),
so it must be good with zero personal data and *better* with it.

**Available for every order (the workhorse signals):**
- **Cart context** — what's already in the basket (the strongest signal).
- **Time of day** — breakfast / lunch / afternoon / dinner / late.
- **Day of week** — weekday solo vs. weekend group.
- **Store / location & type** — mall food-court vs. standalone.
- **Dine mode** — dine-in vs. takeaway.
- **Promotions** — the active promo calendar.

**Available only when logged in (personalization bonus):**
- **Purchase history** — favourite items/combos, reorder patterns.
- **Loyalty tier** — Thành Viên / Vàng / Bạch Kim.

**What actually powers it in this build:**
- `products` — the real KFC catalog (92 items, categories, prices, tags like `drink`/`side`/`dessert`/`chicken`/`combo`).
- `transactions` — item-level order history (synthetic now, real KFC POS later via a one-file adapter). This is the training data.
- `assocrules` — market-basket rules mined offline from `transactions`.
- (logged-in) the member's own rows in `transactions`.

---

## 3. Algorithm level — a graceful-degrading ensemble

No single technique wins, so five layers stack; cheapest/most robust first. If
the fancy layers are unavailable, the basic ones still return good results.

**L1 — Market-basket association rules (the backbone).**
Offline, we mine rules like `{fried chicken} → {Pepsi}` from `transactions`
using **FP-Growth** (support / confidence / lift). At serve time we look up
rules whose antecedent is a subset of the current cart and rank candidates by
`lift × confidence`. Fully explainable ("61% of people who bought X added Y"),
sub-millisecond, no cold-start for popular items. *This alone can hit the AOV
target.*

**L2 — Contextual "complete-the-meal" popularity.**
A rule-free safety net: if the cart is missing a category (no drink? no side?
no dessert in the afternoon?), suggest the contextually-appropriate bestsellers
for that gap. Guarantees a sensible suggestion even when no association rule
matches.

**L3 — Item embeddings + vector similarity (optional).**
Each menu item is embedded (name + category + description + tags) with a small
multilingual model into Qdrant. Used to broaden the candidate pool with
semantically similar/complementary items and to power semantic menu search.
Skipped safely if Qdrant isn't running.

**L4 — Personalization re-rank (logged-in only).**
Given the candidate pool, boost items the member has bought before (affinity
from their `transactions` history). Anonymous sessions skip this entirely.

**L5 — LLM re-rank + Vietnamese copywriter (OpenAI, optional).**
Over the *candidate set only*, an LLM (a) picks the best 1–3 given full context
and (b) writes a short persuasive VN line ("Thêm Pepsi mát lạnh cho combo trọn
vị nhé!"). **Guardrail:** every item the LLM returns is validated against the
candidate set — anything it invents is dropped. So it never suggests an
off-menu or out-of-stock item; it only *reorders and phrases* what the
algorithms already chose. If no API key, we fall back to template copy.

**Ordering:** L1 + L2 generate candidates → (L3 optionally adds more) → merge &
dedupe, drop items already in cart → L4 personalizes (if logged in) → L5 ranks
+ writes copy. Each response also reports `explain.strategies_used` so you can
see which layers fired.

---

## 4. System / technical setup — how it's wired

```
 Kiosk (React)                      Backend (Express)                 Reco service (FastAPI)          MongoDB
 ─────────────                      ─────────────────                 ──────────────────────         ───────
 add item / open cart ──POST /api/recommend──▶ proxy (recoClient) ──POST /recommend──▶ ensemble ──▶ products
   (slot + context)                 hydrates cartId → cart lines       L1..L5 pipeline               assocrules
   renders RecoStrip  ◀── enriched recs ◀──── enrich w/ product docs ◀── ranked recs ◀────────────── transactions
                                    logs reco_shown event                                             (events written here)
```

- **One endpoint, two front doors:** `POST /api/recommend` on the backend serves both the kiosk and (later) the chat agent. The backend is a thin proxy that hydrates the cart and forwards to the FastAPI reco service, then enriches results with live product price/image.
- **Offline job:** `python -m app.mine_rules` reads `transactions`, mines FP-Growth rules per context (all / per-time-of-day / per-dine-mode), and writes them to `assocrules`. Re-run periodically (or on a schedule) — not on every order.
- **Graceful degradation:** if the reco service or OpenAI/Qdrant is down, the backend returns an empty list rather than blocking checkout; if only OpenAI/Qdrant are down, L1+L2 still serve. (The backend now waits up to 8s and caches the product catalog for 120s to avoid re-fetching remote Mongo on every call.)
- **Telemetry:** every shown/accepted/declined recommendation is written to `events` — the basis for measuring AOV uplift and, later, a contextual bandit that learns which slot/offer actually converts.

### One request, end to end (trace)
1. Kiosk sends `{slot:"item_added", context:{cartId, timeOfDay, dineMode, storeId, channel, userId}}`.
2. Backend hydrates `cartId` → the cart's line items (`sku`, `qty`) and forwards to reco.
3. Reco builds the candidate pool: L1 rules matching the cart → L2 complements → (L3) → merge, drop in-cart items.
4. If `userId` present, L4 boosts the member's past favourites.
5. L5 picks top N and writes VN copy (or templates if no key), validated against candidates.
6. Reco returns `[{sku, name, price, reason, copy, strategy, score}]` + `explain.strategies_used`.
7. Backend attaches live product image/price, logs `reco_shown`, returns to the kiosk, which renders the strip. Tapping "+ Thêm" logs `reco_accepted`.

---

## 5. Reading the output (for demos)

- `strategy: "assoc_rule"` + reason "…% khách mua cùng" → came from mined co-purchase data.
- `strategy: "context_pop"` + reason "Thêm nước uống cho trọn bữa" → complete-the-meal fallback.
- `strategy` containing `+llm_rerank` → the LLM reordered/phrased it.
- `explain.strategies_used` lists every layer that contributed.

Demo tip: add a **bare fried-chicken piece** with no drink → you'll get a drink
suggestion; add the drink → the next suggestion moves to a side/dessert. That
visibly shows the cart-aware logic.

---

## 6. Limits & roadmap

- **Feedback loop (near-term):** kiosk orders currently update loyalty but aren't appended to `transactions`, so a just-placed order doesn't yet grow that member's personalization history. Adding an order→`transactions` append closes this loop live; association rules stay a periodic re-mine.
- **Contextual bandit (stretch):** use `events` (accept/decline as reward) to learn which slot and which offer convert best.
- **Real data (drop-in):** when KFC provides real POS exports, map their columns to the `transactions` schema (one adapter), re-run mining — nothing downstream changes. The synthetic data has deliberate co-occurrence structure so the pipeline behaves realistically until then.
- **The LLM is polish, not foundation:** by design the system is reliable at checkout without OpenAI; the LLM only improves ranking and phrasing over a safe candidate set.
