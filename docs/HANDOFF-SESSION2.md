# P4 Zalo Agent — Session 2 Handoff (2026-07-12)

Current-state handoff for continuing the Zalo OA conversational ordering agent.
Read this together with `ZALO-HANDOFF.md` (original deploy) and `ZALO-SETUP.md`
(ops runbook). This doc supersedes the "Next steps" of `ZALO-HANDOFF.md`.

## TL;DR status

The Zalo OA agent is **live and the full delivery order flow works end to end**:
greeting → browse menu by category → contextual combo recommendations → add to
cart → delivery address → voucher suggestion + apply → confirm → choose **COD or
QR** → (QR) receive a **real scannable QR image** → scan → **payment webhook marks
the order paid and pushes a confirmation** back in Zalo. Verified in a real chat
on 2026-07-12.

**Two known issues remain (details below):** (1) a member-identity linking bug
(phone given at checkout doesn't durably link the Zalo id → member), and (2) the
chat context window is unbounded (whole history replayed every turn).

## What works now (verified in live Zalo chat)

- Natural greeting, **no pushy login prompt** (login only asked on intent).
- "Xem menu" → `list_categories` shows the real category groups; agent asks party
  size and offers combo recommendations.
- Protein/health-aware combo recommendations, add-to-cart, drink up-sell.
- Delivery address capture (free text: address + recipient name + phone).
- Proactive voucher step: lists active codes, recommends the best applicable one,
  applies on confirm.
- Cart read-back + explicit confirm before `place_order`.
- **COD**: order placed + confirmed instantly.
- **QR**: order created *pending* → scannable QR image sent → scanning hits
  `/zalo/pay` → backend marks paid → "đơn đang giao" confirmation pushed.

## What changed this session

### Infra / bug fixes
- **`reco/.env` `BACKEND_URL` was `http://localhost:3000` but the backend runs on
  `:3100`** → every backend tool call (menu, cart, link, reco) returned empty and
  the agent said "chưa lấy được...". Fixed to `http://localhost:3100`.
  ⚠️ This gets reset whenever the backend is re-deployed/re-cloned — re-check it
  after any backend deploy.
- **Zalo send `-201 user_id is invalid`** was a token/OA mismatch (access token
  not bound to the OA receiving messages). Fixed by re-running OAuth consent
  (`/zalo/oauth/login`) for the correct OA.
- Added webhook debug logging in `main.py`: raw event + `bad_signature` + a
  `[zalo] <user>: '<text>' -> '<reply>'` line per turn.

### Features built
- **Delivery framing**: prompt + `create_cart` + greeting no longer ask
  "dine-in/takeaway"; this is a delivery channel. New `dineMode: "delivery"`.
- **Menu by category**: new `list_categories` tool (→ `/api/menu/categories`);
  prompt shows groups first, asks party size, offers combos; never searches the
  literal word "menu".
- **Phone-only linking (no OTP)**: `POST /api/channel/link` requires phone only;
  `link_channel` tool + schema take just `phone`; creates the member if new.
- **Deterministic login gate** (in `loop.py` `_run_tool`): member-only tools
  (`check_loyalty`, `my_orders`, `reorder_last`) return `needs_link` when
  unlinked; `place_order` returns a one-time optional pitch per order (customer
  can decline and still check out anonymously). No proactive first-turn pitch.
- **Proactive voucher** step in the checkout prompt.
- **Delivery address**: `Cart`/`Order` models gain `deliveryAddress`,
  `contactName`, `contactPhone`; `PATCH /api/carts/:id` accepts them; order
  snapshot includes them; new `set_delivery` tool.
- **COD + QR payment**: `Order.payment.method` enum `mock|cod|qr`, status
  `pending|paid`; `orderService` sets QR→pending; new `POST /api/orders/:id/pay`
  (idempotent) to settle.
- **QR pipeline (reco)**: `zalo.send_image` (CS media attachment);
  `GET /zalo/pay/qr` renders the QR PNG; `GET /zalo/pay` marks paid + pushes
  confirmation; payment tokens in Mongo `zalo_payments`; `place_order` mints the
  token + QR URL for `method: "qr"`; `loop` surfaces the image URL and `main`
  sends it after the text reply. New dep: **`qrcode[pil]`**.

## Files changed this session

**Backend** (`/var/www/kfc/backend`, restart `kfc-backend`):
`src/models/Cart.js`, `src/models/Order.js`, `src/routes/carts.js`,
`src/routes/orders.js`, `src/services/orderService.js`, `src/routes/channel.js`

**Reco** (`/var/www/kfc/reco`, restart `kfc-reco`):
`app/config.py`, `app/main.py`, `app/agent/loop.py`, `app/agent/registry.py`,
`app/agent/tools.py`, `app/agent/zalo.py`, `requirements.txt`

## Open issues / next steps (priority order)

### 1. Member identity linking bug (HIGH)
After a customer gives their phone at the `place_order` optional pitch, the order
is created and points are awarded, **but the durable `channel_identities` link
(zaloId → member) is not established**, so a later message ("kiểm tra tài khoản")
isn't recognized and re-asks for the phone. `state.userId` also doesn't persist
across the following turn.

Puzzle: points are only awarded when `cart.userId` is set, which normally means
`link_channel` ran (creates user + attaches cart + upserts the linked identity).
So either `link_channel` isn't being called (order attributed via the delivery
phone some other way) or the identity write/read isn't round-tripping.

**Diagnostic to run first** (VPS, reco venv):
```bash
cd /var/www/kfc/reco
sudo -u www-data .venv/bin/python - <<'PY'
from app.agent.tools import link_channel, resolve_identity
from app.db import get_db
db = get_db()
ext = "8490255535787064711"   # the test Zalo user id
print("channel_identity:", db.channel_identities.find_one({"externalId": ext}))
s = db.sessions.find_one({"sessionId": ext}) or {}
print("session state:", s.get("state"), "| #messages:", len(s.get("messages", [])))
t = "diag-link-001"
print("LINK   :", link_channel("zalo", t, "0912300099"))
print("RESOLVE:", resolve_identity("zalo", t))
db.channel_identities.delete_one({"externalId": t})
PY
```
- `channel_identity` is `None` → `link_channel` never ran on the checkout-phone
  path. Fix: in the `place_order` pitch flow, require `link_channel(phone)` before
  re-calling `place_order` when the customer provides a number (prompt + possibly
  a gate that links the phone from the pending order/delivery contactPhone).
- identity exists + `linked` but `state.userId` null → loop isn't loading it;
  check `resolve_identity` / the `chat()` recognition path.
- `LINK linked:true` but `RESOLVE linked:false` → backend link/resolve mismatch.

### 2. Unbounded chat context window (HIGH)
`loop.chat` replays the **entire** `messages` array to the LLM every turn (no
cap). Sessions already hit ~67 messages → rising cost/latency and eventual
context-limit failure. Add a rolling window (keep system message(s) + last
~16–20 messages) and optionally a short running summary of older turns. Persist
as today via `save_session`.

### 3. `send_image` URL-attachment fallback (MEDIUM)
`zalo.send_image` sends the QR as a media attachment by URL. Some Zalo API
versions require uploading the image first (upload API → attachment token) rather
than a raw URL. Watch `journalctl -u kfc-reco -f` for `[zalo] send_image failed`;
if it fails, implement the upload-first path. (Text flow works regardless.)

### 4. Minor
- `get_item`/combo detail doesn't expose what's inside a combo (customer asked
  "combo có tinh bột không" → agent couldn't answer precisely). Enrich combo
  contents if time allows.
- COD/QR both award points at placement; QR points are granted before payment
  settles (acceptable for demo; move to `/pay` if strict).

## Deploy & ops (recap)

- VPS `momolita` (163.223.211.160). Backend `:3100` (loopback), reco `:8080`
  (loopback), nginx proxies **only** `/zalo/` on `pawgrammers.io.vn` (TLS via
  certbot). Shared MongoDB `api.pawgrammers.io.vn`, db `kfc`.
- Public routes (all under `/zalo/`): `/zalo/webhook`, `/zalo/oauth/login`,
  `/zalo/oauth/callback`, `/zalo/pay`, `/zalo/pay/qr`.
- Deploy = SFTP changed files into `/var/www/kfc/{backend,reco}`, then:
  ```bash
  cd /var/www/kfc/reco && .venv/bin/pip install -r requirements.txt   # qrcode dep
  sudo chown -R www-data:www-data /var/www/kfc
  sudo systemctl restart kfc-reco kfc-backend
  ```
- After ANY backend redeploy: re-check `reco/.env` has
  `BACKEND_URL=http://localhost:3100`, and `curl -s localhost:3100/api/admin/stats`
  returns products:92.
- Watch a live turn: `sudo journalctl -u kfc-reco -f`.
- Chat sessions live in Mongo `kfc.sessions` (keyed by Zalo user id). Payment
  tokens in `zalo_payments`. OA tokens in `zalo_tokens`.

## Architecture (unchanged)

```
Zalo user → OA → POST /zalo/webhook (reco) → verify sig → parse user_send_text
  → chat(sessionId = zalo user_id) → tools → backend :3100 → Mongo
  → reply (send_text) [+ QR image via send_image]
QR scan → GET /zalo/pay → POST backend /api/orders/:id/pay → push confirmation
```
The agent loop is channel-agnostic; all Zalo transport is isolated in
`reco/app/agent/zalo.py`.
