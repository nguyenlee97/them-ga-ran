# P4 — Zalo OA Integration & Deploy Guide

Wires the (already channel-agnostic) chat agent to the **IOT Generation** OA via
the **Pawgrammers** Zalo App. The adapter lives in the FastAPI `reco` service —
the same process that already hosts `chat()` and `/agent/ui`, so there's no extra
hop.

## What was added

| File | Change |
|---|---|
| `reco/app/agent/zalo.py` | **new** — token manager (auto-refresh + Mongo persistence), OAuth PKCE consent, webhook signature verification, event parser, CS send-message |
| `reco/app/main.py` | `POST /zalo/webhook` (+ `GET` health), `GET /zalo/oauth/login` + `GET /zalo/oauth/callback` (PKCE consent → token re-seed), `GET /` domain-verify landing page, `GET /{fname}.html` static verifier serving |
| `reco/app/config.py` | `ZALO_*` config |
| `reco/.env` / `.env.example` | Zalo credentials (real values in `.env`, gitignored) |
| `reco/public/` | drop the downloaded domain-verification file here (file method) |
| `backend/src/server.js` | optional `HOST` env (bind `127.0.0.1` in prod to keep the backend private) |

No new Python dependencies — `httpx` was already used by the agent tools.

### How it flows
```
Zalo user → OA → webhook POST /zalo/webhook (reco)
  → verify X-ZEvent-Signature (SHA256(appId+body+timestamp+OAsecret))
  → parse user_send_text → chat(sessionId=zaloUserId) → reply
  → POST openapi.zalo.me/v3.0/oa/message/cs (access_token auto-refreshed)
```
The webhook returns **200 immediately**; the LLM turn + reply run in a background
task so Zalo never times out. Each Zalo user id is the chat `sessionId`, so carts
and login persist across turns exactly like the web harness.

### Tokens
Access tokens live ~1h and **refresh tokens rotate on every use**. On first boot
the seed tokens in `.env` are copied into Mongo (`zalo_tokens`); after that the
adapter refreshes ~5 min before expiry (or on a token error) and persists the new
pair. You don't need to touch `.env` again unless the refresh token fully expires
(~3 months idle) — then re-run the OAuth consent (`/zalo/oauth/login`, §5).

---

## 0. Pre-flight — make sure nothing collides (read-only)

This deploy is additive (loopback-only ports, path-scoped nginx location, new
systemd units, new Mongo collections), but confirm these three before changing
anything:
```bash
# 1) Is :8080 free?  (empty = free; if taken, pick another port and update BOTH
#    the systemd ExecStart and nginx proxy_pass below)
sudo ss -ltnp | grep -E ':(80|443|3000|8080)\b'

# 2) Is nginx the front-end, and does anything already answer for the root domain?
nginx -v 2>&1 ; systemctl is-active nginx apache2
sudo nginx -T 2>/dev/null | grep -nE 'server_name|listen '

# 3) Does the ROOT domain point at THIS VPS? (the two IPs must match)
dig +short pawgrammers.io.vn ; curl -s ifconfig.me
```
Back up nginx before editing so it's trivially reversible:
`sudo cp -r /etc/nginx /etc/nginx.bak`.

> **Verified state on `momolita` (163.223.211.160):** shared box (adspilot / agent
> / api / baomoi-stg / n8n / zingmp3-stg / znews-stg …). `:8080` free ✓, `:3000`
> **already taken** by another node app (so the KFC backend uses `:3100`), and
> **no server block for the bare root** `pawgrammers.io.vn` (all existing blocks
> are subdomains → we add a new root block cleanly). Everything binds `127.0.0.1`;
> only the `/zalo/` path is ever exposed.

## Getting the code onto the VPS

Unlike a static `/var/www` site (files nginx serves directly), the backend and
reco are **long-running processes** — you copy the files AND run them under
systemd (which keeps them alive across crashes/reboots).

Two ways to get the files there — **either** is fine:
- **git (recommended, easiest updates):**
  `sudo mkdir -p /var/www/kfc && cd /var/www/kfc && git clone <repo-url> .`
  Future updates = `git pull` + `systemctl restart kfc-backend kfc-reco`.
- **SFTP (Bitvise, your usual):** drag `backend/` and `reco/` into `/var/www/kfc/`.
  **Exclude `node_modules/`, any `venv/`/`.venv/`/`__pycache__`** — those are built
  on the server (below), not copied.

Then fix ownership so the service user can read them:
`sudo chown -R www-data:www-data /var/www/kfc` (keep `.env` files `chmod 640`).

## 1. Deploy the KFC Express backend (internal only)

`:3000` is taken, so run it on a **free port** bound to loopback — reco reaches it
over localhost; it needs no nginx block. Confirm the port is free:
`sudo ss -ltnp | grep :3100` (empty = free).

`backend/.env` (recreate on the VPS — gitignored). `HOST=127.0.0.1` keeps it
private (needs the `HOST` support in `src/server.js`):
```
PORT=3100
HOST=127.0.0.1
MONGODB_URI=mongodb://agent_user_1:pawngrammers@api.pawgrammers.io.vn:27017/kfc?authSource=admin
RECO_URL=http://localhost:8080
NODE_ENV=production
```
`/etc/systemd/system/kfc-backend.service` — set `ExecStart` to your real node path
(`which node`; nvm installs it outside `/usr/bin`). **No inline comments on
directive lines** — systemd treats a trailing `# ...` as part of the value:
```ini
[Unit]
Description=KFC ordering backend (Express)
After=network.target

[Service]
WorkingDirectory=/var/www/kfc/backend
ExecStart=/usr/bin/node src/server.js
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```
```bash
cd /var/www/kfc/backend && npm ci --omit=dev
sudo chown -R www-data:www-data /var/www/kfc/backend
sudo systemctl daemon-reload && sudo systemctl enable --now kfc-backend
sudo ss -ltnp | grep 3100                 # expect 127.0.0.1:3100 (not *:3100)
curl -s localhost:3100/api/admin/stats    # products:92, assocRules>0
```
The shared Mongo was already seeded during dev — do **not** re-seed unless empty.

## 2. Deploy the reco service on the VPS

Recreate `reco/.env` (gitignored — copy the `ZALO_*` block from your local `.env`).
**On this VPS set `BACKEND_URL=http://localhost:3100`** to match the backend port.
Config is read from `reco/.env` via `load_dotenv()` (WorkingDirectory pins the CWD).

Install deps into an **isolated virtualenv** — Ubuntu blocks system-wide pip
(PEP 668), and on a shared box a venv avoids disturbing the system Python other
apps use. Do NOT use `--break-system-packages`.
```bash
cd /var/www/kfc/reco
sudo apt install -y python3.12-venv        # only if `venv` below fails
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
sudo chown -R www-data:www-data /var/www/kfc/reco   # service user owns the venv
```
`/etc/systemd/system/kfc-reco.service` (ExecStart points at the **venv** uvicorn;
again, no inline comments on directive lines → an invalid `User` gives 217/USER):
```ini
[Unit]
Description=KFC reco + Zalo agent (FastAPI)
After=network.target

[Service]
WorkingDirectory=/var/www/kfc/reco
ExecStart=/var/www/kfc/reco/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now kfc-reco
sudo ss -ltnp | grep 8080              # uvicorn listening
curl -s localhost:8080/health          # {"ok":true,"service":"kfc-reco","llm":true}
```
Binding `127.0.0.1` keeps reco off the public interface — only nginx (same host)
reaches it. The backend (`:3100`) must also be running — the agent's tools call it.

## 3. nginx reverse proxy + TLS on pawgrammers.io.vn

Host the webhook on the **root `pawgrammers.io.vn`** — already verified in the Zalo
App and otherwise unused, so the domain-verification step is skipped. Proxy only
`/zalo/`, leaving the rest of the domain (and reco's `/recommend`, `/agent/ui`,
`/docs`) unexposed. DNS already resolves to this VPS, and there is no existing
server block for the bare root, so we add one cleanly.

Put this in the same place as your other sites (`/etc/nginx/sites-available/` +
symlink, or `/etc/nginx/conf.d/`):
```nginx
server {
    listen 80;
    server_name pawgrammers.io.vn;

    # Only the Zalo webhook + OAuth callback are exposed.
    location /zalo/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/kfc-zalo.conf /etc/nginx/sites-enabled/   # if using sites-*
sudo nginx -t && sudo systemctl reload nginx          # -t gates the reload; other sites keep serving
curl -s http://pawgrammers.io.vn/zalo/webhook         # {"ok":true,"service":"kfc-zalo-webhook"}
sudo certbot --nginx -d pawgrammers.io.vn             # adds :443 block + auto-renew (choose redirect)
curl -s https://pawgrammers.io.vn/zalo/webhook        # same JSON over https
```

## 4. Verify the domain — SKIP

`pawgrammers.io.vn` is already verified in the Zalo App, so nothing to do here.
(The `GET /` meta-tag page and `reco/public/` file-serving remain as fallbacks but
aren't needed; `ZALO_VERIFY_META` in `.env` is harmless.)

## 5. Configure the webhook (Zalo App console → Official Account → Webhook)

- **Webhook URL:** `https://pawgrammers.io.vn/zalo/webhook`
- **Register events:** at least `user_send_text` (text message) and `follow` (sends
  the greeting). `user_send_image` / `user_send_sticker` are ignored gracefully.
- Ensure the app has **Send Message (v3)** permission for the OA.

### OAuth callback (token re-consent)

Lets the OA admin (re)grant consent in a browser and have reco capture a fresh
token pair automatically — no hand-pasting when the refresh token eventually dies.

- **Register the Callback URL** in the console (App → Official Account / Login):
  `https://pawgrammers.io.vn/zalo/oauth/callback`
  It must match `ZALO_REDIRECT_URI` in `reco/.env` exactly.
- **To run consent:** open `https://pawgrammers.io.vn/zalo/oauth/login` in a browser
  as the OA admin → approve → Zalo redirects to the callback → reco exchanges the
  code (PKCE) and stores the new `access_token` + `refresh_token` in Mongo. You'll
  see "✅ Zalo OA linked".

Not needed for day-to-day operation (tokens auto-refresh) — it's the recovery path.

## 6. End-to-end test

**Signature + parsing (unit-tested locally):** valid MAC accepted, tampered/absent
rejected, `dev bypass` when `ZALO_OA_SECRET` unset. **PKCE** validated (S256).

**Live smoke test:** from a Zalo account, follow **IOT Generation** (expect the
greeting), then send "cho mình 1 combo gà rán". Watch the turn:
```bash
sudo journalctl -u kfc-reco -f          # [zalo] token refresh / send + the chat turn
```

**Simulate a signed event locally** (drives webhook → chat → send; the send hits
the real Zalo API):
```bash
APPID=990183335072014581; OASECRET=nRzqmcZUq7uqYRzqIn2C
BODY='{"app_id":"'$APPID'","event_name":"user_send_text","sender":{"id":"<yourZaloUserId>"},"recipient":{"id":"oa"},"message":{"text":"chào","msg_id":"m1"},"timestamp":"1752200000000"}'
MAC=$(printf '%s' "$APPID$BODY""1752200000000$OASECRET" | sha256sum | cut -d' ' -f1)
curl -s -X POST http://127.0.0.1:8080/zalo/webhook \
  -H "Content-Type: application/json" -H "X-ZEvent-Signature: mac=$MAC" \
  -d "$BODY"        # -> {"ok":true}
```

## Notes / troubleshooting
- **502 Bad Gateway from nginx:** reco isn't listening on `:8080` — check
  `systemctl status kfc-reco` and `journalctl -u kfc-reco`. Common cause: an inline
  `# comment` after a systemd directive (e.g. `User=www-data  # ...`) → `217/USER`.
- **401 / error -216 / -124 on send:** access token expired — the adapter refreshes
  and retries once; if it still fails the refresh token is dead → re-consent at
  `/zalo/oauth/login`.
- **`bad_signature` (403):** OA Secret mismatch, or a proxy mutating the body. The
  nginx `proxy_pass` above forwards the body untouched.
- **No reply but 200 logged:** check the backend (`:3100`) is up and reachable at
  reco's `BACKEND_URL`, and `OPENAI_API_KEY` is set in `reco/.env`.
- **Backend on `*:3100` instead of `127.0.0.1:3100`:** `HOST=127.0.0.1` missing from
  `backend/.env`, or the updated `server.js` isn't deployed. Fix + restart.
- **CS messages** only reach users inside the allowed interaction window; during a
  live chat that's always satisfied.
