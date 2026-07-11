# Test Plan — what we've built & how to verify it

Everything added since the personalization sprint (2026-07-11), in the order
you should test it. Each step has a pass criterion. Total time: ~30–40 min.

---

## 0. What's built (inventory)

| # | Component | Where | Status |
|---|---|---|---|
| 1 | Persona-based synthetic seed (6 personas, cadences, 3 demo accounts, stats/tier recomputed from history) | `backend/seed/personas.js`, `users.seed.js`, `transactions.seed.js` | built, **needs seed run** |
| 2 | Order→transactions feedback loop (every order appended, fire-and-forget) | `backend/src/services/transactionService.js` + `orderService.js` | built, needs test |
| 3 | L4 personalization v2: recency decay (30d half-life) × context match (time/dine/store) + category backoff + cold-start scaling | `reco/app/pipeline/personalize.py`, `config.py` | built, needs test |
| 4 | L1 category de-dup (cart with Pepsi → no more 7Up; combo counts as drink+side) + promo/"new" boost | `reco/app/pipeline/ensemble.py` | built, needs test |
| 5 | Metrics: `GET /api/admin/metrics` + dashboard page; combo upgrades now logged (`combo_upgrade_accepted`) | `backend/src/routes/admin.js`, `metricsDashboard.js`, `recommend.js`, `kiosk RecoStrip.jsx` | built, needs test |
| 6 | P4 agent core hardened (session cartId/userId restore + injection, mid-order member link, cart cleared after order, compact tool responses) | `reco/app/agent/loop.py`, `tools.py` | built, needs test (OpenAI key) |
| 7 | Web chat harness (dev rig + demo fallback; simulates Zalo channel) | `reco/app/agent/chat_ui.py`, `main.py` → `/agent/ui` | built, needs test (OpenAI key) |
| — | Zalo OA webhook adapter | — | deferred until OA credentials collected |

**Demo accounts** (any login code works):

| Phone | Name | Persona → expected recs lean |
|---|---|---|
| `0900000001` | An Gà Rán | fried chicken + Pepsi + fries |
| `0900000002` | Bích Tráng Miệng | desserts, afternoon |
| `0900000003` | Cường Gia Đình | family combos, weekend dinner, drinks/desserts ×n |

---

## 1. Prerequisites

- [ ] Paste the Mongo password into `backend/.env` AND `reco/.env` (replace `<PASTE_PASSWORD>`).
- [ ] Optional but needed for chat agent + L5 copy: `OPENAI_API_KEY` in `reco/.env`.
- [ ] Reco/mining always via the **Python 3.12** interpreter, never bare `python` (3.10).
- [ ] Do **NOT** run `python -m app.mine_rules` — it overwrites the curated rules.

## 2. Re-seed (REQUIRED — new persona data)

```
cd backend && npm run seed
```

Pass criteria (console output):
- [ ] `[seed:users] inserted 63 members (3 demo accounts, persona-based)`
- [ ] `[seed:transactions] inserted ~8000 transactions (~1000–1400 identified persona visits, rest anonymous)`
- [ ] `[seed:transactions] recomputed stats/tier/points for ~63 members`
- [ ] `[seed:rules]` inserts curated rules (>0)

Then start everything:
```
cd reco   && <python3.12> -m uvicorn app.main:app --port 8080
cd backend && npm start
cd kiosk  && npm run dev
```

Sanity: open `http://localhost:3000/api/admin/stats` → products 92, users 63,
transactions ≈8000, assocRules >0.

## 3. Anonymous kiosk flow (regression — nothing should have broken)

- [ ] Attract → dine-in → skip login → menu renders with real photos.
- [ ] Add a fried chicken item → item-added modal shows recs: expect a **drink** (assoc rule) + side/dessert; NO combos in the strip.
- [ ] **NEW — category de-dup:** add a Pepsi to the cart, reopen recs (go to cart) → NO other drink suggested (7Up etc.). Same for a second dessert once one is in cart.
- [ ] Combo trade-up card ("Nâng cấp lên Combo") still appears for chicken carts and swap works.
- [ ] Add a combo to cart → recs suggest dessert/snack, never drink/side (combo covers them).

## 4. Personalization (the headline)

**4a. Different members, different recs.**
- [ ] Log in as `0900000002` (Bích, dessert persona). Add 1 chicken piece → recs should lean dessert, ideally with reason prefix **"Món bạn hay gọi —"** or **"Hợp gu bạn —"**.
- [ ] New session, log in as `0900000001` (An). Same chicken → recs lean Pepsi/fries with the personal prefix.
- [ ] (API check) `POST /api/recommend` with `context.userId` set → response `explain.strategies_used` contains `personalize`, and `explain.personalization` shows `n_history` > 20 for demo accounts.

PowerShell one-liner (replace `<USERID>` from the login response):
```powershell
Invoke-RestMethod -Uri http://localhost:3000/api/recommend -Method Post -ContentType "application/json" -Body '{"slot":"cart","context":{"timeOfDay":"afternoon","dineMode":"dine_in","cart":[{"sku":"<any-chicken-sku>","qty":1}],"userId":"<USERID>"},"limit":3}' | ConvertTo-Json -Depth 5
```

**4b. Cold start.**
- [ ] Log in with a fresh phone (e.g. `0912345678`, auto-creates member) → recs identical to anonymous, `explain.strategies_used` has `personalize_cold_start` (or no personalize), nothing weird.

**4c. Live feedback loop (the demo money-shot).**
- [ ] Note `transactions` count (`/api/admin/stats`).
- [ ] As the fresh member, order 2–3 desserts and pay (mock).
- [ ] `transactions` count +1.
- [ ] Place a second order or two of desserts → then add a chicken piece to a new cart → dessert recs should now rank higher for this member (recency-weighted: minutes-old orders carry near-full weight). `explain.personalization.n_history` grows with each order.
- [ ] Anonymous order also appends a transaction (count grows; `userId: null`).

## 5. Metrics dashboard

- [ ] Open `http://localhost:3000/api/admin/dashboard` — loads, mostly zeros at first.
- [ ] Do a kiosk session: view recs (impressions↑), tap "+ Thêm" on a rec (accepted↑), do a combo upgrade (combo accepted↑), place the order.
- [ ] Refresh: acceptance rate >0, strategy table populated, combo panel counts, **AOV table splits orders with/without accepted recs** and shows uplift % once you've placed both kinds of orders (one with an accepted rec, one plain).
- [ ] Window switcher (24h / 7 ngày / Tất cả) works.

## 6. Chat agent (needs `OPENAI_API_KEY` in `reco/.env`)

Open `http://localhost:8080/agent/ui`:

- [ ] "Cho mình 2 miếng gà giòn cay và 1 pepsi" → tool chips show `search_menu` → `create_cart` → `add_to_cart`; reply lists items + prices from backend (never invented).
- [ ] Agent proactively suggests an add-on (get_recommendations) without being pushy.
- [ ] "Mình là thành viên, sđt 0900000001" → `link_channel` fires; loyalty info correct; cart now tied to the member.
- [ ] "Chốt đơn nhé" → agent reads back cart + total FIRST, waits for explicit confirm, then `place_order` → order id + points. (Confirm-before-commit.)
- [ ] Send another message → session remembers you; ordering again creates a **new** cart (old one cleared).
- [ ] "Tôi muốn khiếu nại, cho gặp nhân viên" → `handoff` fires.
- [ ] Chat order appears in `/api/admin/stats` orders AND transactions (feedback loop covers chat too — channel `zalo`).

## 7. Known quirks

- Whole-repo CRLF/LF churn in `git status` — from the clone, add a `.gitattributes` before committing.
- Cowork sandbox mount lags behind host files during editing sessions; host files are authoritative (irrelevant when running yourself).
- Reco service must be up BEFORE testing kiosk recs (backend proxy waits up to 8s, then returns empty).
- First `/api/recommend` call after reco restart is slower (product cache cold).

## 8. What's intentionally NOT done yet

- Zalo OA webhook adapter (blocked on OA credentials — checklist: approved OA + API access, access token, webhook registration for `user_send_text`, send-message API v3 permissions).
- Kiosk greeting reorder slot ("Đặt lại đơn yêu thích?").
- Demo-reset endpoint, demo script, pitch deck.
- EN i18n decision (finish vs hide toggle).
