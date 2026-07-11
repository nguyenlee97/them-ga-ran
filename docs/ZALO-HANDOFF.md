# P4 Zalo OA — Session Handoff / Walkthrough

> ⚠️ **Newer state exists:** read `docs/HANDOFF-SESSION2.md` (2026-07-12) first —
> it supersedes the "Next steps" below (delivery + COD/QR payment now built; two
> known bugs documented). This doc remains the original deploy record.

Context for resuming P4 in the main conversation. This session took the P4 chat
agent from "core done, transport pending" to **deployed and live on Zalo**. The
companion doc `ZALO-SETUP.md` is the step-by-step deploy runbook; this doc is the
"what we did + current state + what's next" summary.

## What was accomplished

The channel-agnostic `chat()` agent (in `reco/app/agent/loop.py`) is now reachable
from the real Zalo OA **IOT Generation** via the **Pawgrammers** Zalo App. A user
messages the OA → the agent replies with real menu/cart/order actions. Verified
working: webhook receives events, agent runs a turn, replies are delivered, tokens
auto-refresh, and the browser OAuth consent flow re-seeds tokens.

## Architecture (transport only — the agent itself is unchanged)

```
Zalo user → OA (IOT Generation)
  → HTTPS POST https://pawgrammers.io.vn/zalo/webhook
  → nginx (root domain, location /zalo/) → 127.0.0.1:8080 (reco / uvicorn)
  → verify X-ZEvent-Signature → parse user_send_text
  → chat(sessionId = zalo user_id) → tools hit backend 127.0.0.1:3100 → Mongo
  → reply → POST openapi.zalo.me/v3.0/oa/message/cs (access_token auto-refreshed)
```
Key design choices: webhook returns **200 immediately**, the LLM turn + send run in
a FastAPI **BackgroundTask** (Zalo won't time out). The **Zalo user id is the chat
`sessionId`**, so carts/login persist per user exactly like the web harness. All
Zalo-specific code is isolated in `reco/app/agent/zalo.py`; the agent loop stays
transport-agnostic.

## Code added/changed (all in `reco/`, except one backend line)

| File | What |
|---|---|
| `app/agent/zalo.py` | **new.** Token manager (`get_access_token`, `_refresh`), OAuth PKCE consent (`start_consent`, `finish_consent`, `_new_pkce`), `verify_signature`, `parse_event`, `send_text`. Tokens persisted in Mongo `zalo_tokens`; OAuth state in `zalo_oauth`. |
| `app/main.py` | Routes: `POST /zalo/webhook` (+ `GET` health), `GET /zalo/oauth/login`, `GET /zalo/oauth/callback`, `GET /` (verify meta tag), `GET /{fname}.html` (verifier file). `_handle_zalo_message` background handler. |
| `app/config.py` | `ZALO_*` settings (ids, secrets, tokens, endpoints, redirect URI). |
| `.env` / `.env.example` | `ZALO_*` values (real ones in gitignored `.env`). |
| `backend/src/server.js` | Added optional `HOST` env → bind `127.0.0.1` in prod. |

No new dependencies (`httpx` already used).

## Deployment state (VPS `momolita`, 163.223.211.160 — shared box)

| Piece | Value |
|---|---|
| Backend | `/var/www/kfc/backend`, systemd `kfc-backend`, node → `127.0.0.1:3100` |
| Reco | `/var/www/kfc/reco`, systemd `kfc-reco`, uvicorn (`.venv`) → `127.0.0.1:8080` |
| nginx | new server block `pawgrammers.io.vn`, `location /zalo/` → `:8080`, TLS via certbot |
| Public URL | `https://pawgrammers.io.vn/zalo/webhook` (only path exposed) |
| OAuth callback | `https://pawgrammers.io.vn/zalo/oauth/callback` (registered in console) |
| MongoDB | shared `api.pawgrammers.io.vn`; new collections `zalo_tokens`, `zalo_oauth`, plus chat `sessions` |
| Zalo App | Pawgrammers, `app_id 990183335072014581`; OA IOT Generation; secrets in `reco/.env` |

Both services bind loopback; only nginx `/zalo/` is public. Restart after code
changes: `sudo systemctl restart kfc-reco` (and `kfc-backend`).

## Gotchas learned (so they don't bite again)

- **systemd `217/USER`:** no inline `# comments` after a directive — `User=www-data # x`
  makes the whole string the username. Keep directive lines clean.
- **PEP 668 (`externally-managed-environment`):** use a **venv** on this shared box,
  not `--break-system-packages`; point `ExecStart` at `.venv/bin/uvicorn`.
- **502 from nginx** = reco not on `:8080` (service crashed / wrong `ExecStart`).
- **`curl -I` → 405** on `/zalo/oauth/login` is normal (HEAD not allowed; route is GET).
- **OAuth:** always start at `/zalo/oauth/login` (it makes `state` + PKCE challenge);
  hand-built permission URLs fail with "Missing code/state".
- **PKCE encoding unverified against live docs** (JS-rendered). Implemented standard
  S256 (`base64url(sha256(verifier))`) — matches Zalo's JS SDK. If consent ever errors
  on the challenge, that's the single knob, isolated in `_new_pkce()`.

## Next steps for further implementation

1. **Member identity linking (biggest one).** Right now each Zalo user is a fresh
   session; orders aren't tied to a KFC member. Implement: resolve the OA-scoped
   Zalo id → member via a `channel_identities` collection **on every message**; for
   unlinked users, a one-time "link your number" pitch that runs `link_channel`
   (phone + code) and attaches the member to the open cart. Keep `zalo.py` as the
   transport owner. (See project memory: *KFC: Zalo identity flow*.)
2. **Rich replies.** Upgrade `send_text` → Zalo v3.0 template/attachment messages
   (product cards, quick-reply buttons, list of combos) instead of plain text, for a
   demo-quality ordering UX. Reco already returns structured recs/combo-upsell.
3. **Non-text events.** `user_send_image` / `user_send_sticker` are currently ignored;
   add a friendly nudge or basic handling. `follow` already sends a greeting.
4. **CS message window.** OA "customer service" messages are only deliverable inside
   the allowed interaction window; fine during live chat, but any proactive/push
   messaging (order-ready, promos) needs a message-tag/ZNS path — design later.
5. **Ops polish.** `deploy.sh` for one-command redeploy; log/metrics for Zalo turns
   (reuse the admin dashboard); consider a systemd `EnvironmentFile` audit.

## How to verify it's live
```bash
sudo journalctl -u kfc-reco -f      # watch a real turn: POST /zalo/webhook 200 + [zalo] send (error:0)
curl -s https://pawgrammers.io.vn/zalo/webhook            # {"ok":true,"service":"kfc-zalo-webhook"}
```
Then message the OA from a personal Zalo account.
