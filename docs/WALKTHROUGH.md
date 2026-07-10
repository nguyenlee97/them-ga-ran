# KFC Hackathon — Walkthrough

Where the project stands, and exactly what to do next. Read top to bottom once.

---

## 1. What's been built (done ✅)

A complete code scaffold for **both tracks over one backend**. Nothing has been
run against your DB yet — the sandbox I built this in can't reach your VPS.

| Part | Path | Status |
|---|---|---|
| Strategy & design | `docs/DESIGN.md` | ✅ |
| Detailed build plan | `docs/BUILD-PLAN.md` | ✅ |
| **Backend** (Express + MongoDB) | `backend/` | ✅ code complete |
| **Reco service** (FastAPI ensemble) | `reco/` | ✅ code complete |
| **Chat agent** scaffold (P4) | `reco/app/agent/` | ✅ ready, Zalo wiring later |
| **Kiosk** replica (React + Vite) | `kiosk/` | ✅ code complete |
| **Menu scraper** + fallback catalog | `scraper/` | ✅ |
| **Seed generators** | `backend/seed/` | ✅ |
| **Seed scripts** (win + linux) | `scripts/` | ✅ |
| docker-compose | `docker-compose.yml` | ✅ |
| Live DB seeded | your Mongo `kfc` | ⬜ **you run this (step 3)** |

Both `backend/.env` and `reco/.env` are already pointed at:
`mongodb://agent_user_1:****@api.pawgrammers.io.vn:27017/kfc?authSource=admin`
(the `camp_ads` db swapped for `kfc`). These files are gitignored.

### What the backend gives you
Menu, stores, auth (mock phone login), server-side carts, **idempotent** order
commit, simple loyalty stats, stubbed vouchers, a `/api/recommend` proxy,
event logging, and a handoff endpoint. This is the single surface the kiosk and
the chat agent both call.

### What the reco service gives you
`POST /recommend` runs a graceful-degrading ensemble:
association rules → contextual complete-the-meal → optional embeddings →
personalization (logged-in) → optional OpenAI rerank + Vietnamese copy (with a
hallucination guard). If OpenAI/Qdrant aren't configured, it still works.

### What the kiosk gives you
Attract → Login (skip allowed) → Menu → Cart → Checkout, with AI recommendation
strips at the item-add, cart, and checkout moments; VI/EN; mock payment +
points confirmation.

---

## 2. Prerequisites (install once)

On the machine that can reach your Mongo (your laptop or the VPS):

- **Node.js 18+** and npm — for backend, kiosk, scraper.
- **Python 3.11+** and pip — for the reco service + rule mining.
- (Optional) **Docker** — only if you'd rather run via `docker compose`.
- (Optional) an **OpenAI API key** — only to enable the LLM copy/rerank layer.

> ⚠️ Important: I could **not** connect to `api.pawgrammers.io.vn:27017` from my
> build environment (its network only allows an allowlist, and your VPS isn't on
> it). So every step below must run somewhere that can reach that host — your own
> machine or the VPS. Nothing here needs my environment.

---

## 3. Seed the database (the main thing you asked for)

### Option A — one command (recommended)

From the project root `kfc-track-hackathon/`:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\seed.ps1
```

**Linux / macOS / VPS / Git-Bash:**
```bash
bash scripts/seed.sh
```

This installs backend deps, seeds the `kfc` db (menu + 10 stores + 60 members +
vouchers + ~8,000 synthetic transactions), then installs the reco deps and mines
the association rules.

Useful flags: `--scrape` (fetch the live KFC menu first), `--no-rules` (skip
mining), `--index` (also build the Qdrant vector index).
PowerShell equivalents: `-Scrape`, `-NoRules`, `-Index`.

### Option B — manual, step by step

```bash
# 1) (optional) scrape the live menu — else the curated 33-item fallback is used
cd scraper && npm install && npx playwright install chromium && node scrape_menu.js && cd ..

# 2) seed the database
cd backend && npm install && npm run seed && cd ..

# 3) mine the recommendation rules
cd reco && pip install -r requirements.txt && python -m app.mine_rules && cd ..
```

**What seeding does to your DB:** it clears and repopulates ONLY these
collections in the `kfc` db — `products`, `stores`, `users`, `vouchers`,
`transactions` (and `assocrules` when mining). It never touches `camp_ads` or
other databases. Re-running is safe (idempotent).

You can tune volume with an env var: `SEED_TX_COUNT=15000 npm run seed`.

---

## 4. Verify the seed worked

Start the backend and hit the admin stats endpoint:

```bash
cd backend && npm start
# in another terminal:
curl http://localhost:3000/api/admin/stats
# → {"products":33,"stores":10,"users":60,"transactions":~8000,"assocRules":NNN,"orders":0}

curl http://localhost:3000/api/admin/rules?limit=10   # top mined rules by lift
```

If `assocRules` is 0, run the mining step (3) — the reco engine's L1 layer needs
it. `products`/`stores`/`transactions` should all be non-zero.

---

## 5. Run the whole thing locally (optional, to see it work)

```bash
# terminal 1 — backend (uses backend/.env → your kfc db)
cd backend && npm start                      # :3000

# terminal 2 — reco service (uses reco/.env → your kfc db)
cd reco && uvicorn app.main:app --port 8080  # :8080

# terminal 3 — kiosk UI
cd kiosk && npm install && npm run dev        # http://localhost:5173
```

Open the kiosk in a browser, add a chicken item, and watch the recommendation
strip suggest a drink/side with a reason. That's the P2 demo.

To enable the AI-written Vietnamese upsell copy (L5), put an OpenAI key in
`reco/.env` (`OPENAI_API_KEY=sk-...`) and restart the reco service. Without it,
you still get recommendations with template copy.

---

## 6. What's next (roadmap)

1. **You:** run the seed (step 3) and verify (step 4). Tell me the
   `/api/admin/stats` numbers so I know it took.
2. **Then:** we run it end-to-end and I fix any runtime bugs (this is the first
   actual execution, so expect a couple).
3. **Enrich reco (M5):** turn on embeddings + OpenAI copy, add AOV-uplift
   measurement from the `events` collection.
4. **Chat agent (M6):** test `POST /agent/chat` with an OpenAI key, refine the
   tool flow and confirm-before-commit.
5. **Zalo OA (M7):** you guide the webhook + the phone-number identity mapping
   (`channel_identities`), and we go live on chat.
6. **Swap in real KFC data** when the organizers provide it — write one adapter
   mapping their POS export to the `transactions` schema, re-run mining. Nothing
   downstream changes.

---

## 7. Troubleshooting

- **`MongoServerError: Authentication failed`** — check the password/`authSource=admin`
  in `backend/.env` and `reco/.env`.
- **Can't connect to Mongo** — you must run from a host that can reach
  `api.pawgrammers.io.vn:27017` (your machine/VPS, not a restricted sandbox).
- **`assocRules: 0`** — run `python -m app.mine_rules`. If still 0, lower
  `MIN_SUPPORT` / `MIN_CONFIDENCE` in `reco/.env` (more data also helps —
  raise `SEED_TX_COUNT`).
- **Reco returns empty** — make sure the reco service is running and
  `RECO_URL` in `backend/.env` points to it (`http://localhost:8080`).
- **Playwright scrape returns 0 items** — the KFC DOM changed; adjust the
  `SELECTORS` block in `scraper/scrape_menu.js`, or just use the fallback
  `menu.sample.json` (default).
- **Stray `kiosk/node_modules`** — a leftover from my tooling; safe to delete,
  `npm install` will rebuild it.

---

## v2 update — faithful kiosk UI + real KFC menu

The kiosk was rebuilt to match the real kiosk screenshots, and the menu now uses
the **real KFC Vietnam catalog** (92 items, real prices/descriptions/photos,
scraped from kfcvietnam.com.vn).

**What changed**
- Welcome screen: the **Ăn tại chỗ / Mua mang về** buttons are the entry action; login is now a **modal popup** over the welcome page (not a separate page).
- Menu page: real category rail (Ưu Đãi, Món Mới, Combo 1 Người, Combo Nhóm, Gà Rán - Gà Quay, Burger - Cơm - Mì Ý, Thức Ăn Nhẹ, Thức Uống & Tráng Miệng), product cards with real photos + prices + descriptions.
- Cart & checkout: rebuilt to match (member banner, promo row, totals, footer).
- `scraper/menu.json` + `scraper/menu.sample.json` now contain the 92 real items with real image URLs (`static.kfcvietnam.com.vn/images/items/lg/<CODE>.jpg`).

**To pick up the real menu in your DB, re-seed + re-mine** (products/skus changed):

```powershell
# from project root
powershell -ExecutionPolicy Bypass -File scripts\seed.ps1
```

Or manually: `cd backend && npm run seed`, then re-mine rules with your 3.12 python:
`cd ../reco && <python3.12> -m app.mine_rules`.

**Run the kiosk**
```bash
cd kiosk
npm install
npm run dev        # http://localhost:5173
```

**Marketing images (optional):** drop `welcome-hero.png` (1080×1400) and
`menu-banner.png` (1080×264) into `kiosk/public/assets/`. See `docs/IMAGE-ASSETS.md`.
Styled fallbacks render if they're absent; product photos need nothing (live from KFC CDN).
