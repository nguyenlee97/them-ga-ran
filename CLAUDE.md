KFC Track Hackathon — an AI product for two tracks over ONE backend:
(P2) a contextual recommendation engine for KFC self-ordering kiosks, and
(P4) a conversational ordering agent for Zalo/Messenger (backend + agent
scaffold ready; Zalo wiring later).

Stack: Express + MongoDB "ordering brain" (menu, carts, idempotent orders,
loyalty, vouchers, /api/recommend proxy, events); a Python/FastAPI reco service
(graceful-degrading ensemble: curated menu-grounded association rules →
complete-the-meal → optional embeddings → personalization → optional OpenAI
rerank+VN copy, plus a combo trade-up module); a React+Vite+Tailwind kiosk that
faithfully replicates the real KFC VN kiosk; and a Playwright menu scraper.
Uses the REAL KFC Vietnam menu (92 items, real prices/photos). VI primary, EN
secondary. Payment is mocked. Shared MongoDB on a VPS.

Code + full context live in the GitHub repo (folders: backend, reco, kiosk,
scraper, scripts, docs). Read docs/HANDOFF.md first — it has architecture,
current state, credentials/setup, and next steps. docs/DESIGN.md,
BUILD-PLAN.md, RECOMMENDATION-EXPLAINED.md, WALKTHROUGH.md, MONGO-SETUP.md and
CONVERSATION-LOG.md have the rest. Be concise and direct.