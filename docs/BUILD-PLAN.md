# KFC Hackathon — Detailed Build Plan

**Companion to:** `DESIGN.md` (system design & strategy)
**Scope of this plan:** everything through the kiosk demo + chatbot-ready backend. Zalo OA integration is planned but executed last, under Nguyên's guidance.
**Confirmed decisions baked in:** mocked payment · DOM scrape of the menu · kiosk personalization = logged-in only · Zalo identity via phone-mapping (schema now, flow later) · VI primary / EN secondary · vouchers deferred (stub) · loyalty = simple member stats.

---

## 0. Guiding principles

1. **One backend, two front doors.** Kiosk (P2) and chat (P4) are thin clients over the same Express+MongoDB core + one FastAPI reco/agent service.
2. **Data-source-agnostic.** Everything runs on synthetic data now; a single adapter swaps in KFC's real POS export later. No downstream code changes.
3. **Backend is the source of truth.** Prices, totals, stock, order commit — always server-side. The LLM proposes; the backend enforces.
4. **Reuse Claw-a-thon patterns** (`random-bullshlt`): Express routes/models/services shape, `order_api.py` idempotency, Qdrant hybrid RAG, `fastembed` (CPU), docker-compose.
5. **Every step is demoable.** P2 is fully shippable before we touch the chat agent.

---

## 1. Repository layout

```
kfc-track-hackathon/
├── docs/
│   ├── DESIGN.md                 # strategy (this plan's companion)
│   └── BUILD-PLAN.md             # this file
├── backend/                      # Express + MongoDB — the "ordering brain"
│   ├── src/
│   │   ├── server.js
│   │   ├── db.js                 # mongo connection
│   │   ├── models/               # Mongoose schemas
│   │   │   ├── Product.js  Store.js  User.js  Cart.js
│   │   │   ├── Order.js    Voucher.js  Transaction.js
│   │   │   ├── AssocRule.js  Event.js  ChannelIdentity.js
│   │   ├── routes/
│   │   │   ├── menu.js     stores.js  auth.js  carts.js
│   │   │   ├── orders.js   loyalty.js vouchers.js  recommend.js
│   │   │   ├── events.js   handoff.js  admin.js
│   │   ├── services/
│   │   │   ├── cartService.js    # totals, combo integrity, stock
│   │   │   ├── orderService.js    # idempotent commit, points/stats update
│   │   │   ├── loyaltyService.js  # simple member stats
│   │   │   └── recoClient.js      # proxy to FastAPI reco service
│   │   └── middleware/ (auth, error, requestLog)
│   ├── seed/
│   │   ├── menu.seed.js           # loads scraped menu → products
│   │   ├── stores.seed.js         # ~10 representative stores
│   │   ├── users.seed.js          # synthetic members + tiers
│   │   └── transactions.seed.js   # synthetic POS history (the reco fuel)
│   ├── package.json  Dockerfile  .env.example
├── reco/                         # Python + FastAPI — reco + (later) chat agent
│   ├── app/
│   │   ├── main.py               # FastAPI, /recommend, /health
│   │   ├── config.py
│   │   ├── pipeline/
│   │   │   ├── assoc_rules.py    # L1 market-basket mining + serve
│   │   │   ├── context_pop.py    # L2 conditional bestsellers
│   │   │   ├── embeddings.py     # L3 (fastembed, reuse Claw-a-thon)
│   │   │   ├── personalize.py    # L4 history re-rank (logged-in)
│   │   │   └── llm_rerank.py     # L5 OpenAI rank + VN copy + guardrail
│   │   ├── mine_rules.py         # offline job → writes assoc_rules to Mongo
│   │   └── agent/                # P4 — built later
│   │       ├── registry.py       # OpenAI tool schemas (VI)
│   │       ├── tools.py          # httpx wrappers to backend
│   │       ├── loop.py           # tool-calling orchestration
│   │       └── session.py        # Mongo-backed chat memory
│   ├── requirements.txt  Dockerfile  .env.example
├── kiosk/                        # React + Vite + Tailwind — P2 UI replica
│   ├── src/ (screens: Attract, Login, Menu, ItemModal, Cart, Checkout)
│   ├── src/i18n/ (vi.json, en.json)
│   └── package.json  vite.config.js
├── scraper/
│   └── scrape_menu.js            # Playwright DOM scrape → menu.json
├── docker-compose.yml            # mongo, backend, reco, qdrant (+ optional obs)
└── README.md
```

---

## 2. Data model (Mongo collections + key indexes)

| Collection | Purpose | Key fields / indexes |
|---|---|---|
| `products` | Menu catalog (scraped) | `sku`(uniq), `category`, `isCombo`, `tags`, `available` |
| `stores` | ~10 representative restaurants | `_id`, `type`, `city`, `district` |
| `users` | Members + **simple loyalty stats** | `phone`(uniq), `tier`, `pointsBalance`, `stats{visitCount,totalOrders,totalSpend,firstOrderAt,lastOrderAt}` |
| `channel_identities` | Zalo/Messenger id → member map | uniq `(channel, externalId)`, `phone`, `userId`, `status` |
| `carts` | Live baskets (server-side) | `channel`, `storeId`, `userId?`, `items[]`, `totals`, `status` |
| `orders` | Committed orders | **uniq `idempotencyKey`**, `status`, `payment`, `pointsEarned` |
| `transactions` | Synthetic POS history (reco fuel) | `storeId`, `ts`, `timeOfDay`, `dineMode`, `lines[]` |
| `assoc_rules` | Precomputed market-basket rules | `antecedent[]`, `consequent`, `support`, `confidence`, `lift`, `context` |
| `vouchers` | Promo codes (stubbed) | `code`(uniq), `type`, `conditions`, `active` |
| `events` | Reco impressions/accepts + telemetry | `type`, `slot`, `strategy`, `ts` |
| `sessions` | Chat agent memory (P4) | `sessionId`, `messages[]` |

Full field lists are in `DESIGN.md §4`. Schema is written **first** so seed + scraper target a fixed contract.

---

## 3. Backend API surface (Express)

| Method + path | Used by | Notes |
|---|---|---|
| `GET /api/menu` · `GET /api/menu/:id` · `GET /api/menu/search` | kiosk, agent | catalog + search (search proxies embeddings) |
| `GET /api/stores` | kiosk, agent | list / nearest |
| `POST /api/auth/login` | kiosk, agent | phone + code (mock OTP); returns member |
| `POST /api/carts` · `GET /api/carts/:id` | both | create / read cart |
| `POST /api/carts/:id/items` · `DELETE /api/carts/:id/items/:lineId` | both | mutate cart (server recomputes totals) |
| `POST /api/carts/:id/voucher` | both | apply voucher (stub validation) |
| `POST /api/orders` | both | **idempotent commit** → mock pay → update user stats/points |
| `GET /api/orders/:id` | both | status |
| `GET /api/loyalty/:userId` | both | simple stats (visits, cumulative orders/spend, rank, points) |
| `POST /api/recommend` | kiosk, agent | proxies to FastAPI reco service |
| `POST /api/events` | kiosk, agent | log reco shown/accepted/declined |
| `POST /api/handoff` | agent | escalate to human (P4) |
| `GET /api/admin/*` | us | inspect seed/rules for the demo |

**Order commit rules:** unique index on `idempotencyKey`; retry-once-safe (Claw-a-thon `order_api.py`); on success recompute `user.stats` + award points by tier (3/5/7%).

---

## 4. Recommendation service (FastAPI) — `POST /recommend`

Ensemble, graceful-degrading (see `DESIGN.md §2.3`). Request/response contract in `DESIGN.md §2.6`.

- **L1 `assoc_rules`** — offline `mine_rules.py` runs FP-Growth (`mlxtend`) over `transactions`, writes rules to `assoc_rules`. Serve = lookup by cart antecedents, rank by lift×confidence. Works day one.
- **L2 `context_pop`** — grouped top-attach items by `(timeOfDay, dineMode, storeType, cartCategories)`. Fallback when no rule matches.
- **L3 `embeddings`** — `fastembed` MiniLM(384-d)+BM25 into Qdrant; complementary/similar candidates + powers `menu/search`.
- **L4 `personalize`** — logged-in only; item-based CF / implicit ALS over the user's history to re-rank candidates.
- **L5 `llm_rerank`** — OpenAI ranks & writes VN copy **over candidates only**; every returned id validated against candidate set, hallucinations dropped + counted. Fallback: skip → serve L1/L2 order.

Each `/recommend` call logs an `event` (slot, strategy, returned items) → AOV-uplift measurement + optional bandit later.

---

## 5. Chat agent backend (P4) — prepared now, wired later

- **Tools** (schemas in `registry.py`, httpx wrappers in `tools.py`): `search_menu`, `get_item`, `get_recommendations`, `create_cart`, `add_to_cart`, `remove_from_cart`, `view_cart`, `apply_voucher`, `check_loyalty`, `place_order`(idempotent), `get_order_status`, `list_stores`, `handoff`. Full mapping in `DESIGN.md §3.2`.
- **Safety:** backend validates everything; confirm-before-commit; handoff on payment/allergen/NLU-fail/human-request.
- **Zalo identity:** `channel_identities` + a "please send your phone number" link step (`link_channel` tool) — schema built now, conversational flow later.
- **This phase = backend + tool endpoints ready + a minimal test chat UI.** No Zalo yet.

---

## 6. Kiosk replica (P2) — React + Vite + Tailwind

Screens matching the photos: **Attract** (KFC Rewards, 3/5/7%, QR, dine-in/takeaway, VI/EN) → **Login** (member QR / phone; skip allowed but personalization = logged-in) → **Menu** (category rail, promo strips, item cards w/ price+points, running total) → **Item modal** (`get_recommendations slot=item_added`) → **Cart** (`slot=cart`, voucher entry, totals) → **Checkout** (`slot=checkout`, mock pay → order confirmation with points earned).

Reco injection moments per `DESIGN.md §2.5`. Money-shot: add 2-piece chicken → contextual drink+side suggestion with reason + live total/points update; side-by-side vs. static "You may also like."

---

## 7. Menu scraper — `scraper/scrape_menu.js`

Playwright headless → load `kfcvietnam.com.vn/menu`, wait for hydration, extract per item: name(VI), category, price, image URL, description if present → `menu.json`. Normalize to `products` shape; `menu.seed.js` loads it. Re-runnable; manual nutrition/tags enrichment where the site lacks it.

---

## 8. Synthetic data generator — `seed/transactions.seed.js`

Produces realistic POS history so association rules find real structure:
- Real scraped items + prices; combos ordered as units.
- Deliberate co-occurrence: ~60% chicken→drink, fries attach, dessert skews afternoon, buckets skew weekend dinner, solo combos weekday lunch.
- ~10 stores (mall vs standalone), 6–12 months, realistic hourly/daily curves.
- Members with varied RFM so personalization has signal.
- **Adapter boundary:** one `mapRealPos(row)` function is the only thing to change when KFC's export lands.

---

## 9. Deployment (VPS)

Reuse Claw-a-thon `docker-compose.yml`: `mongo`, `backend`(3000), `reco`(8080), `qdrant`(6333), optional `prometheus`/`grafana`. PM2 fallback as in your notes. Env via `.env` per service. OpenAI key in `reco/.env`.

---

## 10. Milestones & sequencing

| # | Milestone | Deliverable | Demoable? |
|---|---|---|---|
| **M0** | Scaffold + schema + compose | repos, Mongo models, docker-compose up | infra |
| **M1** | Menu scrape + seed | `products`, `stores`, `users`, `transactions` in Mongo | data browsable |
| **M2** | Backend core | menu/auth/cart/order(idempotent)/loyalty endpoints | API via curl/Postman |
| **M3** | Reco v1 (L1+L2) | `mine_rules.py` + `/recommend` | contextual reco JSON |
| **M4** | Kiosk replica wired | full P2 ordering flow + live reco | **P2 DEMO** |
| **M5** | Reco v2 | embeddings + personalize + LLM copy + events + AOV metric | richer P2 + numbers |
| **M6** | Chat agent backend | tool registry + endpoints + test chat UI | chat orders (test UI) |
| **M7** | Zalo OA | phone-link flow + OA webhook | **P4 DEMO** (with you) |

**Critical path:** M0→M1→M2→M3→M4 delivers the entire P2 track. M5+ enrich; M6–M7 add P4.

---

## 11. Risks & mitigations

- **KFC data never arrives / arrives late** → synthetic-first + adapter means we demo fully without it; real data is a drop-in.
- **Menu site structure changes / hard to scrape** → scraper is isolated; worst case, hand-enter ~40 items into `menu.json`.
- **OpenAI latency/outage at checkout** → L5 is optional; L1/L2 serve instantly without it. Reco endpoint has a hard timeout + fallback.
- **Double-ordering** → idempotency key + unique index (proven in Claw-a-thon).
- **Scope creep on vouchers/loyalty** → explicitly deferred/stubbed per decisions.

---

## 12. What I need from you to start M0

1. **Green light** on this plan (or edits).
2. Confirm folder name: `C:\Users\LENOVO\Desktop\Project\kfc-track-hackathon` (already created).
3. OpenAI API key when we reach M3/M5 (not needed for M0–M2).
4. VPS/Mongo connection details when we're ready to deploy (M0 can run locally in Docker first).
