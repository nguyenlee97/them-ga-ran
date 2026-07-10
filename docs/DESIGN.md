# KFC Track Hackathon — System Design & Strategy

**Tracks:** P2 (AI recommendation engine for self-ordering kiosks) + P4 (Conversational ordering via chat)
**Author:** Nguyên · **Date:** 2026-07-10 · **Status:** Draft v1 (brainstorm)

---

## 0. TL;DR — the one big idea

Both tracks are the **same product with two front doors.** A customer places a KFC order; the only difference is *where* the conversation happens (a kiosk screen vs. a Zalo/Messenger chat) and *how* recommendations are surfaced (inline UI cards vs. natural-language suggestions).

So we build **one backend** — the "ordering brain" — that owns menu, cart, orders, vouchers, loyalty, and a recommendation service. Then:

- **P2 (kiosk)** = a replica kiosk UI that calls the backend's `/recommend` endpoint at the right moments.
- **P4 (chatbot)** = an AI agent that calls the *same* backend through tools (`add_to_cart`, `apply_voucher`, `place_order`, `check_loyalty`, `get_recommendations`, `handoff`).

The recommendation engine is not chatbot-specific and the cart/order logic is not kiosk-specific. Build the shared core once; both tracks become thin clients.

```
                 ┌────────────────────────────────────────────┐
                 │          KFC "Ordering Brain" (backend)      │
                 │  Express + MongoDB                           │
                 │  menu · combos · stores · users · loyalty ·  │
                 │  vouchers · carts · orders · transactions    │
                 │                                              │
                 │  ┌──────────────┐   ┌──────────────────────┐ │
                 │  │ Reco service │   │ Order / cart / voucher│ │
                 │  │ (FastAPI)    │   │ / loyalty APIs        │ │
                 │  └──────┬───────┘   └───────────┬──────────┘ │
                 └─────────┼───────────────────────┼────────────┘
             REST /recommend│            tools (httpx)│REST
              ┌─────────────▼──────┐      ┌───────────▼───────────┐
              │  KIOSK REPLICA     │      │  CHAT AGENT (FastAPI) │
              │  (React web app)   │      │  OpenAI tool-calling  │
              │  P2                │      │  → Zalo OA / Messenger│
              └────────────────────┘      │  P4                   │
                                          └───────────────────────┘
```

This mirrors your Claw-a-thon split (Express backend + FastAPI agent + React frontend) — we're reusing a proven shape, not inventing one.

---

## 1. Reuse from Claw-a-thon (`random-bullshlt`)

You already have battle-tested patterns. We port them, not rebuild them:

| Claw-a-thon asset | Reuse for KFC |
|---|---|
| Express + MongoDB backend (`routes/`, `models/`, `services/`) | Same shape → KFC menu/order/loyalty backend |
| FastAPI agent, `tools/registry.py` (OpenAI function schemas, VI descriptions) | Chat ordering agent tool registry |
| `tools/order_api.py` httpx wrapper + **idempotency key on order create** | Critical — reuse verbatim for `place_order` |
| RAG stack: Qdrant hybrid (dense MiniLM 384-d + BM25 sparse → RRF → rerank → LLM-over-candidates + hallucination guard) | Semantic menu search + one of the reco strategies |
| `fastembed` (ONNX, CPU-only, no torch) | Keeps reco service light on the VPS |
| `docker-compose.yml` (mongo, qdrant, prometheus, grafana, langfuse) | Same compose file, swap service names |
| GreenNode MaaS OpenAI-compatible client (`llm.py`) | Works as-is; we'll point at OpenAI API instead/as well |

**Key architectural inheritance:** the "LLM reasons only over retrieved candidates, then we validate every returned ID against the candidate set and drop hallucinations" pattern from `rag/recommend.py`. That exact safety rail applies to menu recommendations — the LLM must never invent a menu item that isn't on the real KFC menu.

---

## 2. The recommendation problem (P2)

### 2.1 What data is *realistically* available

The brief promises POS transactions, menu catalog, and context signals. Until KFC hands data over, we generate synthetic data that has the **same schema and the same statistical structure** as reality, so swapping in real data is a config change, not a rewrite.

**(A) Signals that exist for EVERY order — no login required (this is the workhorse):**

- **Cart context** — what's already in the basket right now. This is the single strongest signal at a kiosk. ("Has 2-piece chicken + fries, no drink" → recommend a drink.)
- **Time of day** — breakfast / lunch / afternoon snack / dinner / late-night. Ordering patterns differ hugely (combos at lunch, snacks/desserts mid-afternoon, family buckets at dinner).
- **Day of week** — weekday solo vs. weekend group.
- **Store / location** — mall-food-court kiosk vs. standalone; district; urban vs. suburban. Basket composition varies by store.
- **Order channel & dine mode** — dine-in (`Ăn tại chỗ`) vs. takeaway (`Mua mang về`), kiosk vs. chat.
- **Active promotions** — the promo calendar (e.g. the "Zestival 2026" / "Gà Lắc Tiêu Chanh" items visible on the kiosk) biases what's worth surfacing.
- **Basket size / value so far** — drives whether to upsell (add item) or trade-up (bigger combo).

**(B) Signals available ONLY for logged-in / known users (the personalization layer):**

- **Purchase history** — favorite items, favorite combos, avg spend, reorder patterns.
- **Loyalty tier** — Thành viên / Vàng / Bạch kim (3% / 5% / 7% earn). Higher tiers may get richer offers.
- **Dietary lean** — inferred from history (e.g. always picks "Món Xanh Thanh Nhẹ" lighter items, or never orders spicy).
- **Recency/frequency** — RFM-style; churning customer vs. regular.
- **Birthday / member-day** offers (the kiosk already advertises "Ưu đãi sinh nhật" + "15 ngày thành viên").

**Login policy (confirmed):** For the **kiosk**, we focus the personalization story on **logged-in users** — the demo assumes login (member QR / phone), so we can use purchase history for the personalized re-rank. We do *not* build anonymous cross-visit profiling for the kiosk. Anonymous users still get the non-personalized ensemble (association rules + contextual popularity) so the flow never breaks, but the "wow" personalization is a logged-in feature. For **Zalo/Messenger**, identity comes via the phone-number mapping flow (§4 `channel_identities`).

### 2.2 What "user data we could realistically have" looks like

Even for logged-in users, be honest about what KFC actually has:

- Strong: transaction history tied to phone number / member ID, loyalty points & tier, voucher redemption history.
- Medium: coarse location (which stores they visit), device/app usage.
- Weak / usually absent: age, gender, real dietary restrictions, browsing behavior. **Don't design around data we won't get.** Infer soft signals from transactions instead.

### 2.3 Algorithms — a layered ensemble, not one model

No single technique wins. Layer them so each covers the others' weaknesses. Cheapest/most robust first:

**Layer 1 — Market-basket association rules (the backbone).**
Mine `{A} → {B}` co-purchase rules from transaction history (Apriori / FP-Growth, or just item-item co-occurrence with lift & confidence). This is how you get "people who bought fried chicken + fries also bought a Pepsi." Precompute offline, store rules in Mongo, serve in <5 ms. Works day one, fully explainable, no cold-start for popular items. **This alone can plausibly hit the AOV target.**

**Layer 2 — Contextual popularity / conditional bestsellers.**
"Top attach items given (time_of_day, dine_mode, store_type, what's in cart)." A grouped frequency table. Covers the "static menu ignores context" complaint directly and needs no ML. Handles cold items via category-level fallback.

**Layer 3 — Item embeddings + vector similarity (reuse your Qdrant stack).**
Embed each menu item (name + category + description + nutrition + typical co-items). Use it for (a) semantic menu search in the chatbot, and (b) "similar item" and complementary-item retrieval as reco candidates. This is a near-verbatim reuse of `rag/embeddings.py` + `rag/index.py`.

**Layer 4 — Personalization re-rank (logged-in only).**
Given a candidate set from L1–L3, re-rank by the user's affinity (item-based collaborative filtering / implicit-feedback matrix factorization, e.g. `implicit` ALS, or simple user-item score). Only kicks in when we have a user; otherwise skipped.

**Layer 5 — LLM re-ranker / copywriter (OpenAI).**
Two distinct jobs, both over the *candidate set only*:
1. **Rank & justify** — pick the best 1–3 from candidates given full context, and generate a short persuasive VN line ("Thêm 1 ly Pepsi mát lạnh cho combo trọn vị? +7 điểm 🎉").
2. **Guardrail** — every returned item ID is validated against the candidate set; anything invented is dropped (your `RAG_HALLUCINATED` pattern). The LLM never picks items freely — it picks *from* the algorithmic candidates. This keeps recommendations on-menu, in-stock, and promo-aware.

**Why the ensemble is the right story for judges:** it degrades gracefully (if OpenAI is down, L1–L2 still recommend), it's explainable ("bought together 43% of the time"), and it improves automatically as real POS data lands. The LLM is the polish layer, not the foundation — which is exactly right for a system that must be reliable at a checkout.

### 2.4 Optional stretch: contextual bandit for the "right moment"
The brief stresses *"at the right moment in the ordering journey."* A lightweight epsilon-greedy / Thompson-sampling bandit can learn *which slot* (item-add modal, cart page, checkout) and *which offer* actually converts, using accept/decline as reward. Nice differentiator; keep it as a phase-2 flourish, not a blocker.

### 2.5 Where recommendations get injected in the kiosk journey (the "moments")

1. **Item added → modal:** "Ngon hơn khi có… (goes great with)" — attach the missing category (drink/side/dessert).
2. **Category browse → inline "Gợi ý cho bạn" strip** replacing the static "You may also like."
3. **Cart / basket page:** "Hoàn thiện bữa ăn" — complete-the-meal, or trade-up to a combo that's cheaper than à-la-carte.
4. **Checkout / just before payment:** one final low-friction add (dessert, dip, drink upsize).
5. **Logged-in greeting:** "Đặt lại đơn yêu thích?" — reorder shortcut.

Each moment = one call to `POST /recommend` with a `slot` parameter; backend returns ranked items + copy.

### 2.6 Recommendation service API (contract)

```
POST /api/recommend
{
  "slot": "cart" | "item_added" | "checkout" | "browse" | "greeting",
  "context": {
    "storeId": "...", "dineMode": "dine_in|takeaway",
    "timeOfDay": "lunch", "dayOfWeek": "Sat", "channel": "kiosk|zalo",
    "cart": [{ "productId": "...", "qty": 2 }],
    "userId": null | "member_123"          // null = anonymous
  },
  "limit": 3
}
→ 200
{
  "recommendations": [
    { "productId": "...", "name": "Pepsi (vừa)", "price": 25000,
      "reason": "Đi kèm gà rán — 61% khách chọn thêm",
      "strategy": "assoc_rule", "score": 0.61,
      "copy": "Thêm Pepsi mát lạnh cho trọn combo nhé!" }
  ],
  "explain": { "strategies_used": ["assoc_rule","context_pop","llm_rerank"] }
}
```

The **same endpoint** feeds both the kiosk UI and the chat agent's `get_recommendations` tool. Build once.

---

## 3. The conversational ordering problem (P4)

The chatbot is the recommendation engine's twin: instead of rendering cards, it *talks*. Underneath, it does the same four things a kiosk does — browse, build cart, apply offers, pay — plus loyalty and handoff. We only prepare the backend now (per your note); the Zalo integration comes later under your guidance.

### 3.1 Agent shape (reuse Claw-a-thon)

FastAPI service, OpenAI tool-calling loop, MongoDB-backed session memory (`session.py` pattern). System prompt in Vietnamese. The agent is a **thin orchestration layer**: all state lives in the backend cart/order, not in the LLM. The LLM decides *which tool to call*; the backend is the source of truth.

### 3.2 Tools the agent needs (backend must expose these)

This is the crux of "what the backend needs so AI can call tools." Each tool = one backend endpoint + one function schema in the registry (VN descriptions, like your `tools/registry.py`):

| Tool | Backend endpoint | Purpose |
|---|---|---|
| `search_menu(query, filters)` | `GET /api/menu/search` | Find items by name/category/price; powered by embeddings + text. |
| `get_item(productId)` | `GET /api/menu/:id` | Full item detail, modifiers, combo options. |
| `get_recommendations(context)` | `POST /api/recommend` | Same engine as kiosk — upsell/cross-sell in chat. |
| `create_cart(context)` | `POST /api/carts` | Start a cart (store, dineMode, channel). |
| `add_to_cart(cartId, productId, qty, modifiers)` | `POST /api/carts/:id/items` | Add/modify line items. |
| `remove_from_cart(cartId, lineId)` | `DELETE /api/carts/:id/items/:lineId` | Remove item. |
| `view_cart(cartId)` | `GET /api/carts/:id` | Read cart + running total. |
| `apply_voucher(cartId, code)` | `POST /api/carts/:id/voucher` | Validate + apply promo; returns discount or reason for rejection. |
| `check_loyalty(userId)` | `GET /api/loyalty/:userId` | Points balance, tier, earn rate, birthday offer. |
| `place_order(cartId, idempotencyKey, payment)` | `POST /api/orders` | **Commit order — reuse idempotency pattern from `order_api.py`.** |
| `get_order_status(orderId)` | `GET /api/orders/:id` | Track order. |
| `list_stores(location)` | `GET /api/stores` | Nearest store / hours / availability. |
| `handoff(reason, transcript)` | `POST /api/handoff` | Escalate to human staff (complaints, edge cases, payment failure). |

**Design rules that make this safe:**
- **Backend validates everything.** The LLM proposes; the backend enforces price, stock, voucher rules, min-order, and combo integrity. Never trust LLM-computed totals.
- **Idempotent `place_order`** with a client/agent-generated `idempotencyKey` — a timeout must never double-order. (Straight from your Claw-a-thon `create_order`.)
- **Confirm-before-commit.** Agent must read back the cart + total and get explicit user confirmation before calling `place_order` (mirrors your `update_workspace` "propose, don't apply" rule).
- **Handoff conditions:** payment dispute, allergen/safety question, repeated NLU failure, user asks for human, or any tool returns an unrecoverable error.

### 3.3 Success metrics mapping (from P4 brief)
- *Order completion* → % chat sessions reaching a committed `place_order`.
- *Voucher application* → `apply_voucher` success rate.
- *NLU accuracy* → intent/slot eval set (build a small labeled VN test set).
- *Loyalty inquiry* → `check_loyalty` handled without handoff.
- *Order by channel* → `channel` field on every cart/order (kiosk/zalo/messenger) → analytics.

---

## 4. Shared data model (MongoDB)

One database serves both tracks. Collections (fields abbreviated):

**`products`** — the menu catalog (scraped from kfcvietnam.com.vn/menu, then replaced by KFC's real catalog).
```
{ _id, sku, name_vi, name_en, category,           // "Gà Rán", "Combo 1 Người", ...
  price, imageUrl, description, nutrition{kcal,...},
  tags:["spicy","light","new","bestseller"],
  isCombo:false, comboItems:[...], modifiers:[{group,options}],
  available:true, storeAvailability:[...], promoIds:[...] }
```

**`combos`** — or model as `products` with `isCombo:true`. Combo affinity is a first-class reco signal (brief mentions "combo affinity").

**`stores`** — 250+ restaurants: `{ _id, name, address, district, city, type:"mall|standalone", hours, kioskIds:[...] }`.

**`users` / `members`** — `{ _id, phone, name, tier:"member|gold|platinum", pointsBalance, birthday, createdAt,
stats:{ visitCount, totalOrders, totalSpend, firstOrderAt, lastOrderAt } }`. The `stats` block is the "simple loyalty" we surface (times eaten at KFC, cumulative orders/spend, rank). Recomputed on each `place_order`. Anonymous sessions have no user doc.

**`channel_identities`** — maps external chat identities to KFC members (for Zalo OA, which only sees an OA-scoped id, not the phone): `{ _id, channel:"zalo|messenger", externalId:"zaloUserId", phone, userId, linkedAt, status:"pending|linked" }`. Unique index on `(channel, externalId)`. The chat flow asks for phone once, then links. Built now (schema), used fully later.

**`loyalty_ledger`** *(optional, later)* — earn/burn history: `{ userId, orderId, delta, type:"earn|redeem", ts }`. Tier earn rates 3/5/7%. Deferred — for the demo, points are a running counter on the user `stats`; a full ledger comes with real voucher/promo rules.

**`vouchers` / `promotions`** — `{ code, type:"percent|amount|freeItem|combo", value, conditions{minOrder,items,tier,channel,timeWindow}, validFrom, validTo, active }`. Also holds the "promo calendar" context signal.

**`carts`** — live baskets: `{ _id, channel, storeId, dineMode, userId|null, items:[{productId,qty,modifiers,unitPrice}], appliedVouchers:[], totals{sub,discount,grand}, status:"open|ordered|abandoned", createdAt }`.

**`orders`** — committed: cart snapshot + `{ idempotencyKey, status, payment, pointsEarned, placedAt }`. **Unique index on `idempotencyKey`.**

**`transactions`** — the POS history for reco training. Either a view over `orders` or a separate seeded collection of **synthetic historical orders** (line-item level) with realistic time/store/basket distributions. This is what association-rule mining runs on.

**`events`** — telemetry: recommendation shown / accepted / declined, slot, strategy. Powers metrics, the bandit, and the AOV-uplift story. **Log from day one** — this is your evidence at demo time.

**`assoc_rules`** — precomputed market-basket rules: `{ antecedent:[ids], consequent:id, support, confidence, lift, context:{timeOfDay,dineMode} }`. Refreshed by an offline job.

**`sessions`** — chat agent conversation memory (Claw-a-thon `session.py`).

### 4.1 Synthetic data strategy (until KFC delivers)

Build a **seed generator** that produces realistic `transactions`:
- Real menu items (scraped) with real prices.
- Plausible baskets: combos ordered as units; chicken → fries → drink attach patterns; desserts skew afternoon; buckets skew weekend dinner; solo combos at weekday lunch.
- Inject deliberate co-occurrence structure so association rules find *something real* (e.g. 60% of chicken orders attach a drink).
- Spread across ~10 representative stores, 6–12 months, realistic daily/hourly curves.

Isolate all seed logic behind a `seed/` module (like Claw-a-thon's `backend/seed/`). When KFC's CSV/DB arrives, write one adapter that maps their columns to our `transactions` schema and re-run the mining job. **Nothing downstream changes.** Say this explicitly to judges: "our engine is data-source-agnostic; here it is on synthetic data, and here's the 1-file adapter for your real POS export."

---

## 5. The self-ordering kiosk (P2 deliverable)

**Goal now:** a web replica of the KFC kiosk that looks like the photos and calls our backend — recommendations live, everything else functional enough to demo.

### 5.1 What to replicate (from the 4 photos)
- **Attract/registration screen** — KFC Rewards banner, "ĐẶT HÀNG TẠI ĐÂY", 3/5/7% tiers, Zalo/Website QR, dine-in/takeaway toggle, VI/EN switch.
- **Login screen** — scan member QR *or* phone + code, with a prominent **"Bỏ qua" (skip)** → anonymous flow. (Critical: default path is anonymous.)
- **Menu screen** — left category rail (`Món bán chạy`, `Combo 1 Người`, `Combo Nhóm`, `Gà Rán/Gà Quay`, `Mì Ý/Burger/Cơm`, `Món "Xanh" Thanh Nhẹ`, sides, drinks, `Siêu Tiết Kiệm`), promo strips ("CHỚP NGAY ƯU ĐÃI!", "THỬ NGAY KẺO HẾT!"), item cards with price + points badges, running total, `Xem giỏ hàng`.
- **Cart screen** — line items, `Chọn khuyến mãi` / `Nhập mã KM`, totals, member login CTA, `Thanh toán`.

### 5.2 Tech
React + Vite + Tailwind (same as your `agent_frontend`). Portrait layout, touch-sized targets, VI/EN i18n. Vietnamese đồng formatting. It's a stateless client over the backend — cart lives server-side so the chatbot and kiosk could even share a cart later.

### 5.3 Where the AI shows up on the kiosk
Exactly the injection moments in §2.5 — each is a `POST /recommend` call rendering a card strip / modal. The demo money-shot: add a 2-piece chicken → kiosk instantly suggests the contextually-right drink+side with a reason, and the running total + projected loyalty points update. Contrast side-by-side with the current static "You may also like."

### 5.4 Note on the AI agent for the kiosk (later)
The kiosk could *also* embed a conversational assistant later (voice/chat "order for me"), which is literally the P4 agent pointed at `channel:"kiosk"`. That's why we prep the shared backend now — the kiosk agent is free once P4 exists. For this phase: **backend + recommendation cards only.**

---

## 6. Tech stack (recommended)

| Layer | Choice | Why |
|---|---|---|
| Backend / API | **Node.js + Express + MongoDB** | Direct reuse of Claw-a-thon backend; fast to build; one language with the React kiosk. Source of truth for cart/order/voucher/loyalty. |
| Recommendation service | **Python + FastAPI** | Best ecosystem for mining/ML (`mlxtend`/FP-Growth, `implicit` ALS, pandas). Exposes `/recommend`. Reuse Claw-a-thon agent scaffolding. |
| Vector store | **Qdrant** | Already in your compose; hybrid dense+sparse for menu search + similarity reco. |
| Embeddings | **fastembed** (MiniLM multilingual 384-d + BM25) | CPU-only, small — fits the VPS. Your existing choice. |
| LLM | **OpenAI API** (rerank + copy + chat agent) | Per your call. GreenNode MaaS stays as a drop-in OpenAI-compatible fallback. |
| Chat agent | **FastAPI + OpenAI tool-calling** | Reuse `tools/registry.py` + `session.py` patterns. |
| Kiosk frontend | **React + Vite + Tailwind** | Reuse `agent_frontend` setup. |
| Deploy | **Docker Compose on your VPS** (mongo, backend, reco/agent, qdrant, + optional prometheus/grafana) | Your compose file already does this. PM2 fallback as in your notes. |

**Split or merge the Python service?** Start with **one FastAPI service** exposing both `/recommend` and the chat agent (they share menu embeddings + Mongo). Split into two only if load demands it. Keeps the VPS footprint small.

---

## 7. Suggested build sequence

You said: backend → kiosk → recommendation → (Zalo agent last). Refined ordering that de-risks the demo:

1. **Backend core + data model + menu scrape + synthetic seed.** Get `products`, `stores`, `carts`, `orders` (idempotent), `vouchers`, `loyalty` working with REST. *This unblocks everything.*
2. **Recommendation v1 (L1 + L2):** mine association rules from synthetic transactions + contextual popularity. Ship `/recommend`. Cheap, robust, demoable.
3. **Kiosk replica** wired to backend + `/recommend`. This is your P2 demo.
4. **Recommendation v2:** add embeddings (L3) + personalization (L4) + OpenAI rerank/copy (L5) + `events` logging + AOV-uplift measurement.
5. **Chat agent backend:** tool registry over the same endpoints; confirm-before-commit; handoff. (Test via a simple chat UI first.)
6. **Zalo OA integration** — under your guidance, last.

Every step produces something demoable, and P2 is fully shippable after step 3.

---

## 8. Decisions (confirmed)

- **Payment** → **Mocked.** No real gateway; on `place_order` the status flips to `paid` and points are awarded. Keep a clean `payment` field so a real gateway could slot in later.
- **Menu scrape** → **Scrape the DOM** of kfcvietnam.com.vn/menu (small catalog, JS-rendered). Normalize into `products`. One-off script; re-runnable.
- **Kiosk personalization** → **Logged-in only.** The kiosk demo assumes the customer logs in (member QR / phone). We do **not** build anonymous cross-visit profiling for the kiosk. Contextual reco (cart + time + store + promos) still works for everyone; personalized re-rank (history) requires login. Anonymous users still get the non-personalized ensemble (association rules + contextual popularity).
- **Zalo OA identity mapping** → Zalo OA only sees an **OA-scoped user id**, not the real phone number. So the chat flow must **ask the user for their phone number once** and map `zaloUserId → phone → KFC member`. Store this mapping so future chats are auto-linked. (Full member integration is later; design the schema for it now — see §4 `channel_identities`.)
- **Languages** → **VI primary, EN secondary** for kiosk UI, reco copy, and chat.
- **Vouchers** → **Deferred.** Schema/endpoint stubbed but full promo-rule engine can wait for KFC data. `apply_voucher` returns a simple validation for now.
- **Loyalty (simple)** → Show only lightweight member stats: **visit count / times eaten at KFC, cumulative orders, cumulative spend, loyalty rank (tier), points balance.** No complex earn/burn rules engine yet.

---

*Next concrete step (when you're ready): scaffold the backend repo + Mongo schema + menu scraper + synthetic seed generator, so the recommendation and kiosk work has real data to run against.*
