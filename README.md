# KFC Track Hackathon

One backend, two front doors: an **AI recommendation engine for self-ordering kiosks (P2)** and a **conversational ordering agent (P4)** — both over the same Express + MongoDB "ordering brain" and a FastAPI reco/agent service.

See `docs/DESIGN.md` (strategy) and `docs/BUILD-PLAN.md` (build plan).

> Status: code scaffold complete. **Not yet run / tested** — bring up services and seed per below.

## Layout

```
backend/   Express + MongoDB — menu, cart, orders (idempotent), loyalty, vouchers, recommend proxy, events, handoff
reco/      FastAPI — /recommend ensemble (assoc rules → context → embeddings → personalize → LLM) + mine_rules job + P4 chat agent
kiosk/     React + Vite + Tailwind — kiosk replica (P2) with live reco at every moment
scraper/   Playwright DOM scraper for kfcvietnam.com.vn/menu (+ curated fallback menu.sample.json)
docs/      DESIGN.md, BUILD-PLAN.md
docker-compose.yml
```

## Run (local, once dependencies are installed)

1. **Services**

   ```bash
   docker compose up -d          # mongo, backend, reco, qdrant
   ```

   Or run each locally: `cd backend && npm i && npm start`, `cd reco && pip install -r requirements.txt && uvicorn app.main:app --port 8080`.

2. **(Optional) Scrape the live menu** — otherwise the seed uses `scraper/menu.sample.json`:

   ```bash
   cd scraper && npm i && npx playwright install chromium && node scrape_menu.js
   ```

3. **Seed data** (menu, stores, members, vouchers, ~8k synthetic transactions):

   ```bash
   cd backend && npm run seed
   ```

4. **Mine association rules** (reco L1):

   ```bash
   cd reco && python -m app.mine_rules
   # optional vector layer (L3): python -m app.build_index
   ```

5. **Kiosk UI**

   ```bash
   cd kiosk && npm i && npm run dev      # http://localhost:5173
   ```

## Recommendation ensemble (P2)

`POST /api/recommend` → FastAPI. Graceful-degrading layers:
L1 market-basket association rules → L2 contextual complete-the-meal → L3 embedding similarity (optional) → merge → L4 personalization (logged-in) → L5 OpenAI rerank + Vietnamese copy (guardrailed to the candidate set). If OpenAI/Qdrant are down, L1+L2 still serve.

## Chat agent (P4) — backend ready, Zalo later

`reco/app/agent/` has the OpenAI tool registry (VI), httpx wrappers to the backend, session memory, and a tool-calling loop. Test endpoint: `POST /agent/chat`. Zalo OA webhook + phone-number identity mapping (`channel_identities`) are wired later.

## Key decisions baked in

Mocked payment · DOM-scraped menu · kiosk personalization = logged-in only · Zalo identity via phone mapping · VI primary / EN secondary · vouchers stubbed · loyalty = simple member stats (visits, cumulative orders/spend, rank, points).
