# Project Handoff / Resume Context

Read this first to continue the KFC hackathon project in a **new Cowork session or
on another computer**. (Cowork chats don't sync across devices, so this doc + the
repo + the other `docs/` files ARE the portable context.)

## What this project is
Two KFC hackathon tracks over ONE backend:
- **P2** — AI recommendation engine for self-ordering kiosks (primary focus so far).
- **P4** — conversational ordering agent for Zalo/Messenger (backend + agent scaffold ready; Zalo wiring later).

Full strategy in `DESIGN.md`; build plan in `BUILD-PLAN.md`; how recommendations work in `RECOMMENDATION-EXPLAINED.md`.

## Architecture
- `backend/` — Express + MongoDB "ordering brain": menu, stores, auth (mock phone login), carts, idempotent orders, simple loyalty, vouchers (stub), `/api/recommend` proxy, events, handoff, admin. Also `seed/` (menu, stores, users, vouchers, synthetic transactions, **curated association rules**).
- `reco/` — FastAPI recommendation service (`/recommend`) + P4 chat agent scaffold (`app/agent/`). Ensemble: L1 curated association rules → L2 complete-the-meal → [L3 embeddings, off by default] → L4 personalize (logged-in) → L5 OpenAI rerank+VN copy. Plus `combo_upsell.py` (combo trade-up). Offline `mine_rules.py` for real POS data.
- `kiosk/` — React + Vite + Tailwind faithful kiosk replica (Attract → Login modal → Menu → Cart → Checkout) with reco strips + combo trade-up card.
- `scraper/` — Playwright scraper for the real KFC menu; `menu.json` / `menu.sample.json` hold 92 real items (real prices/descriptions/images).

## Services & credentials
- MongoDB (shared VPS): `mongodb://agent_user_1:****@api.pawgrammers.io.vn:27017/kfc?authSource=admin` — set in `backend/.env` and `reco/.env` (gitignored; recreate from `.env.example`). The `agent_user_1` user was granted `readWrite` on the `kfc` db (see `MONGO-SETUP.md`).
- Local ports: backend `:3000`, reco `:8080`, kiosk `:5173`.
- Python on the dev machine: use the 3.12 interpreter that has the deps (the Windows-Store one), not the bare `python` (3.10). Run reco with that interpreter.
- OpenAI key optional (`reco/.env` → `OPENAI_API_KEY`) — only enables the LLM copy/rerank layer; everything works without it.

## Current state (done ✅)
- Real KFC menu scraped + seeded (92 items, real photos).
- Kiosk rebuilt to match the real kiosk screenshots (dine buttons = entry, login is a modal overlay, real category rail, product cards, cart, checkout).
- Recommendation engine working end-to-end with **curated menu-grounded rules** (chicken→Pepsi/fries/dessert; combos→dessert+snack). Sensible, no combos-as-add-ons, category-diverse.
- **Combo trade-up** ("Nâng cấp lên Combo"): parses combo composition, matches the cart, shows price delta, swaps covered items for the combo.
- Cart quantity +/- fixed; cart thumbnails; checkout itemized summary.
- Bug fixes: reco timeout raised to 8s + product cache; L3 embeddings gated off (was loading a model on the request path); drink/dessert mis-tagging fixed.
- **Personalization layer (organizers provide NO data → fully synthetic):**
  - **Persona-based seed** (`backend/seed/personas.js`): 6 personas (gà rán classic, burger lunch, family weekend, dessert snacker, combo solo, ăn nhẹ) with fixed favorites + visit cadences (regular/occasional/lapsed/new); member stats/tier/points recomputed from actual generated history. **Demo accounts** (any login code): `0900000001` An Gà Rán, `0900000002` Bích Tráng Miệng, `0900000003` Cường Gia Đình.
  - **Order→transactions feedback loop** (`transactionService.js`): every placed order is appended to `transactions` (fire-and-forget) — the system learns live during a demo.
  - **L4 v2** (`personalize.py`): recency decay (30-day half-life) × context match (time/dine/store) + category backoff + cold-start scaling below `RECO_MIN_HISTORY` (3). Tunables in `reco/.env` (`RECO_AFFINITY_HALF_LIFE_DAYS`, `RECO_PERSONAL_BOOST`, `RECO_CATEGORY_BOOST`, `RECO_PROMO_BOOST`). `explain.personalization` reports `n_history`/`cold_start`.
  - **L1 category de-dup** (ensemble): complement categories already in the cart (combo counts as drink+side) are no longer suggested. Promoted/"new" items get a small boost for everyone.
  - ⚠️ Requires a **re-seed** (`npm run seed`) — user histories and stats are regenerated.

## How to run (on the new machine)
1. `git clone` the repo; recreate `backend/.env` and `reco/.env` from the `.env.example` files (Mongo URI above).
2. `cd backend && npm install && npm run seed` (loads menu + curated rules).
3. `cd reco && <python3.12> -m pip install -r requirements.txt && <python3.12> -m uvicorn app.main:app --port 8080`.
4. `cd backend && npm start` (`:3000`).
5. `cd kiosk && npm install && npm run dev` (`:5173`).
6. Verify: `curl http://localhost:3000/api/admin/stats` → products 92, assocRules >0.

Do NOT run `python -m app.mine_rules` for the demo — it overwrites the curated rules with sparse synthetic-mined ones (reserve it for real POS data).

## Open threads / next steps
1. **Personalization layer — DONE (see above).** Remaining polish ideas: surface "Đặt lại đơn yêu thích?" reorder shortcut on login greeting; contextual bandit over `events`.
2. **P4 chat agent — core DONE, Zalo transport pending.** Loop hardened (session cartId/userId restore + injection, link_channel attaches member to open cart, cart cleared after place_order, tool responses compacted for tokens). **Web chat harness** at `http://localhost:8080/agent/ui` (simulates the Zalo channel; also the demo fallback). Requires `OPENAI_API_KEY` in `reco/.env`. Remaining: Zalo OA webhook adapter (~100 lines) once user collects: approved OA + API access, OA access token, webhook registration for `user_send_text`, send-message API v3 permissions. **Reco metrics dashboard** also added: `http://localhost:3000/api/admin/dashboard` (AOV uplift, acceptance by slot/strategy, combo trade-up; combo upgrades now logged as `combo_upgrade_accepted`).
3. **EN i18n** — currently partial (VI primary); either fully translate or hide the EN toggle.
4. **Marketing images** — optional `kiosk/public/assets/welcome-hero.png` (1080×1400) and `menu-banner.png` (1080×264); see `IMAGE-ASSETS.md`.
5. **Real KFC POS data** — when provided, map to the `transactions` schema (one adapter) and re-mine; nothing downstream changes.

## Note on the dev environment quirk
Editing tool-written files sometimes lagged the sandbox mount vs. the host; the host files are authoritative (what Vite/Node run). Not relevant on a clean machine.
