# KFC Hackathon — Conversation Log

A faithful reconstruction of the working conversation that produced this project
(reconstructed from context — not a byte-for-byte transcript; huge pasted blobs
like full curl commands, JSON dumps, and image-coordinate lines are condensed).

---

## Turn 1 — Kickoff & brainstorm request
**User:** Participating in the KFC hackathon, choosing two tracks: **P2** (AI-powered product recommendation engine for self-ordering kiosks) and **P4** (AI-powered conversational ordering via chat). Pasted both full problem statements. Context: is a Zalo employee, wants to build the chatbot and, underneath, also tackle the kiosk problem with the same system. Notes:
- Organizers haven't given data yet; build a base we can swap later.
- Use OpenAI API for AI parts, but also want other recommendation techniques.
- Need a mock backend for user DB + menu (menu from https://www.kfcvietnam.com.vn/menu).
- Need a fake self-ordering kiosk site replicating the real one (photos attached).
- Integrate AI chatbot/agent into Zalo OA later (guided later), after backend + kiosk + reco.
- Have a VPS + MongoDB (Claw-a-thon project "random-bullshlt").
Asked me to brainstorm the overall problem, recommendation data/approach, the chatbot backend/tools, the bigger picture of tackling both at once, and how to address the kiosk (backend prep only for now).

**Claude:** Fetched the KFC menu (JS-rendered) and the imported knowledge; asked two clarifying questions — deliverable format and backend stack.

## Turn 2 — Clarifications
**User:** Written design doc; pointed me to the Claw-a-thon project at `C:\Users\LENOVO\Downloads\Claw-a-thon-...\random-bullshlt`, focus on agent + backend.

**Claude:** Studied the Claw-a-thon repo (FastAPI agent with OpenAI-style tool registry, Express+Mongo backend with idempotent order API, Qdrant hybrid-RAG). Wrote **`DESIGN.md`**: the core idea that both tracks are one product with two front doors (one "ordering brain" backend + FastAPI reco/agent; kiosk and chatbot are thin clients). Covered realistic reco data, a layered ensemble algorithm, the chatbot's backend tools, the shared Mongo data model, synthetic-data strategy, and the kiosk plan.

## Turn 3 — Decisions
**User:** Payment mocked; scrape the DOM; kiosk personalization = logged-in only; Zalo identity via phone-number mapping (OA user-id → phone → member); VI primary/EN secondary; vouchers can wait; loyalty = simple stats (visits, cumulative orders, rank…).

**Claude:** Folded all decisions into `DESIGN.md` (added `channel_identities`, simple loyalty stats, login policy). Then asked where to build + whether to plan first.

## Turn 4 — Location + plan-first
**User:** Create the project under `C:\Users\LENOVO\Desktop\Project`; wants a detailed build plan first.

**Claude:** Created `kfc-track-hackathon/` and wrote **`BUILD-PLAN.md`** (repo layout, data model, API surface, reco ensemble, agent tools, kiosk screens, scraper, synthetic seed, docker-compose, 8-milestone plan, risks). Copied `DESIGN.md` alongside.

## Turn 5 — Implement (no tests, no docker run)
**User:** Just implement everything, no tests / no docker run yet.

**Claude:** Built the full scaffold:
- **backend/** — Express + MongoDB: 11 models (incl. `ChannelIdentity`, `AssocRule`, `Transaction`), services (idempotent order commit, cart totals, loyalty, reco proxy), full routes, seed generators, Dockerfile.
- **reco/** — FastAPI ensemble (assoc rules → context → embeddings → personalize → LLM rerank), `mine_rules.py`, `build_index.py`, chat-agent scaffold (tool registry, tools, loop, session).
- **kiosk/** — React + Vite + Tailwind screens.
- **scraper/** — Playwright scraper + curated fallback menu.
- docker-compose + README. Static syntax checks passed.

## Turn 6 — Live Mongo + seed
**User:** Gave the real Mongo URI (`mongodb://agent_user_1:...@api.pawgrammers.io.vn:27017/camp_ads?authSource=admin`); replace `camp_ads` with a `kfc` DB and seed.

**Claude:** Pointed `backend/.env` and `reco/.env` at the `kfc` DB. Discovered the sandbox can't reach the VPS (DNS/allowlist blocked), so seeding must run on the user's machine/VPS.

## Turn 7 — Seed script + walkthrough
**User:** Create a seeding script and a walkthrough of what's done / what's next.

**Claude:** Wrote `scripts/seed.ps1` + `scripts/seed.sh` (one-shot) and **`WALKTHROUGH.md`**.

## Turn 8 — Seed auth error
**User:** Seed failed: `not authorized on kfc to execute command`.

**Claude:** Diagnosed it as a permissions issue (user scoped to `camp_ads`); wrote **`MONGO-SETUP.md`** with the `grantRolesToUser` fix.

## Turn 9 — grant needs auth
**User:** `grantRolesToUser requires authentication`.

**Claude:** Explained they must authenticate as an admin user; steps to find the admin/root creds.

## Turn 10 — getUser null
**User:** `db.getUser("agent_user_1")` returned null.

**Claude:** Told them to `use admin` first (user lives in the admin DB).

## Turn 11 — grant success
**User:** Roles showed `userAdminAnyDatabase`; the grant `readWrite on kfc` succeeded (`ok:1`).

**Claude:** Confirmed; told them to re-run the seed.

## Turn 12 — seed worked, assocRules 0
**User:** `/api/admin/stats` → products 34, stores 10, users 60, transactions 8000, **assocRules 0**. Also noted the kiosk menu wasn't scraped (no descriptions/prices/images) and the UI didn't match the real kiosk; provided reference screenshots and detailed UI corrections.

**Claude:** Explained assocRules 0 = mining hadn't produced rules. Then used the connected browser to scrape the **real KFC menu** (92 items, real prices/descriptions/images, real category structure), installed it, fixed the scraper, and **rebuilt the kiosk to match** the screenshots (dine buttons = entry, login modal overlay, real category rail, product cards, cart, checkout). Wrote `IMAGE-ASSETS.md` with the image sizes to generate.

## Turn 13 — QA the UI (Sonnet subagent)
**User:** Spawn a smaller-model subagent to test the UI at localhost:5173 for bugs.

**Claude:** Ran a Sonnet subagent. Verdict: faithful UI, happy path works; bugs found — cart +/- added/deleted whole lines, empty reco strip (reco service not running), partial EN toggle, generic cart thumbnails, sparse checkout. Fixed the cart quantity endpoint, cart thumbnails, and the checkout itemized summary.

## Turn 14 — login & reco→personalization questions
**User:** Does login work? Does ordering with an account affect recommendations?

**Claude:** Yes login works (mock phone login, points/stats on order). Personalization uses past `transactions` (so logged-in users with history get personalized recs), but a freshly placed order doesn't yet feed back into history — offered to wire the feedback loop.

## Turn 15 — see reco in action
**User:** How to trigger the recommendation flow in the kiosk.

**Claude:** Explained the three moments (item-add, cart, checkout), how to run all three services, and what the reason labels mean.

## Turn 16 — AbortError
**User:** `/api/recommend` returned `reco_unavailable / AbortError`.

**Claude:** Diagnosed the backend's 2.5s proxy timeout vs. remote-Mongo latency; raised timeout to 8s and added a product-catalog cache. Also wrote **`RECOMMENDATION-EXPLAINED.md`** (business → data → algorithm → system, plus problem-coverage and evaluation metrics).

## Turn 17 — still empty (fastembed)
**User:** Still no recs; reco log showed "Fetching 5 files". Asked whether rules use the real menu, and how much of the problem is solved + what metrics.

**Claude:** Root cause: the L3 embedding model was loading on the request path — gated it off by default (`RECO_USE_EMBEDDINGS`). Answered: rules use real menu items but synthetic behavior; explained coverage + metrics (AOV uplift, attach rate, hit-rate@k, A/B, etc.).

## Turn 18 — build realistic rules
**User:** Noticed `assocrules` was empty; time to create realistic rules from the real menu.

**Claude:** Found & fixed a tag bug (drinks mis-tagged `dessert` from the category name). Built **`rules.seed.js`** — curated, menu-grounded rules (chicken→Pepsi/fries/dessert, combo→dessert, trio rule), wired into `npm run seed`; made Python mining opt-in so it wouldn't overwrite curated rules.

## Turn 19 — do the recs make sense?
**User:** Pasted output showing combos recommended as "drinks" — nonsensical.

**Claude:** Fixed three bugs: combos polluting the drink/side pools (now excluded from add-ons; a combo in cart counts as having drink+side), merge losing association-rule priority, and no category diversity. Simulated: chicken → Pepsi + fries + dessert; combo → dessert. Sensible now.

## Turn 20 — combo trade-up + cart-context + personalization
**User:** Asked opinion on (a) "upgrade to combo" suggestions and (b) whether recs avoid redundancy; excited to build personalization next. Also approved making the combo strip fuller.

**Claude:** Made the combo strip fuller (dessert + snack, big buckets + extra drink). Gave opinions (combo trade-up = strong, needs composition parsing + distinct card; redundancy = yes, with one small L1 category gap). Asked what to build next → user chose **Combo trade-up**.

## Turn 21 — build combo trade-up
**Claude:** Built `combo_upsell.py` (parses combo composition, matches cart, price delta, prefers same-item combo), added `comboUpsell` to `/recommend`, and a distinct amber "Nâng cấp lên Combo" card in the kiosk with an upgrade handler that swaps covered items for the combo. Verified: single chicken → "Combo 1 Miếng Gà +22k"; chicken+fries+drink → "save 15k"; Zinger → Zinger combo.

## Turn 22 — moving the project to another computer
**User:** How to move the conversation/context (not code) to another computer.

**Claude:** Explained Cowork sessions don't sync across devices (per docs); move the context via the repo docs + a synced Project. Wrote **`HANDOFF.md`** to let a fresh session resume instantly.

## Turn 23 — export the conversation
**User:** Export the whole conversation to a markdown file.

**Claude:** The live session isn't exposed to the transcript tool, so produced this reconstructed **`CONVERSATION-LOG.md`**.

---

## Artifacts produced (in `docs/` unless noted)
- `DESIGN.md` — strategy & architecture
- `BUILD-PLAN.md` — detailed build plan
- `WALKTHROUGH.md` — run/seed/verify walkthrough
- `RECOMMENDATION-EXPLAINED.md` — how the reco engine works + metrics
- `MONGO-SETUP.md` — granting DB access
- `IMAGE-ASSETS.md` — kiosk image sizes to generate
- `HANDOFF.md` — resume-on-another-machine context
- `CONVERSATION-LOG.md` — this file
- Code: `backend/`, `reco/`, `kiosk/`, `scraper/`, `scripts/`, `docker-compose.yml`
