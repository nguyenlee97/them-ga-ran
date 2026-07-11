# Kickoff prompt — paste this to the next AI

You are continuing work on the **KFC Track Hackathon** project (repo already
present). It has two tracks over one backend: (P2) a kiosk recommendation engine,
and (P4) a **conversational ordering agent on Zalo OA**, which is the current
focus and is already deployed live.

## Read first (in this order)
1. `CLAUDE.md` — project framing and stack.
2. `docs/HANDOFF-SESSION2.md` — **current state, what works, what changed, open
   bugs, deploy notes.** Start here for anything recent.
3. `docs/ZALO-HANDOFF.md` and `docs/ZALO-SETUP.md` — original deploy + ops runbook.
4. `docs/RECOMMENDATION-EXPLAINED.md`, `docs/DESIGN.md` — reco engine + design.

## Stack / where things live
- Backend: Express + MongoDB, `backend/src` (routes, services, models). Source of
  truth for menu, carts, orders, loyalty, vouchers, channel identities, payments.
- Reco + chat agent: Python/FastAPI, `reco/app`. The agent is in
  `reco/app/agent/` (`loop.py` orchestration, `tools.py` backend wrappers,
  `registry.py` tool schemas + system prompt, `zalo.py` Zalo transport,
  `session.py` Mongo-backed chat memory).
- Live on VPS `momolita`: backend `:3100`, reco `:8080`, nginx proxies only
  `/zalo/` on `pawgrammers.io.vn`. Shared MongoDB, db `kfc`.

## Current state (short)
The full Zalo delivery flow works end to end: menu-by-category → combo recs →
cart → delivery address → voucher → confirm → COD or QR → scannable QR image →
payment webhook marks paid + pushes confirmation. See `HANDOFF-SESSION2.md` for
the verified transcript-level detail.

## Your tasks, in priority order
1. **Fix the member-identity linking bug.** When a customer gives their phone at
   the checkout pitch, the order is created + points awarded, but the durable
   `channel_identities` link isn't established, so later turns don't recognize
   them. Run the diagnostic in `HANDOFF-SESSION2.md` §"Open issues 1" FIRST, then
   fix based on which branch it hits (leading hypothesis: `link_channel` isn't
   called on the checkout-phone path).
2. **Cap the chat context window.** `loop.chat` replays the entire message history
   every turn (already ~67 msgs). Add a rolling window (system msgs + last ~16–20)
   and optionally a running summary.
3. **`send_image` fallback.** If `journalctl -u kfc-reco -f` shows
   `[zalo] send_image failed`, implement Zalo's upload-media-first path instead of
   sending the QR by URL.
4. Minor: expose combo contents in `get_item`; consider moving QR point-award to
   the `/pay` settle step.

## Working rules
- **VI primary, EN secondary.** All customer-facing agent text is Vietnamese.
- **Backend is the single source of truth** — tools must never invent prices,
  menu items, or totals; always call the backend.
- Keep all Zalo-specific code in `reco/app/agent/zalo.py`; the agent loop stays
  channel-agnostic.
- Be concise and direct. Payment is mocked (simulated QR webhook). Uses the REAL
  KFC Vietnam menu (92 items).
- After ANY backend redeploy, re-verify `reco/.env` has
  `BACKEND_URL=http://localhost:3100` (it silently resets and breaks all tools).

## Deploy & verify
```bash
# SFTP changed files into /var/www/kfc/{backend,reco}, then on the VPS:
cd /var/www/kfc/reco && .venv/bin/pip install -r requirements.txt
sudo chown -R www-data:www-data /var/www/kfc
sudo systemctl restart kfc-reco kfc-backend
curl -s localhost:3100/api/admin/stats            # products:92
sudo journalctl -u kfc-reco -f                    # watch a live turn
```
Then message the OA (IOT Generation) from a personal Zalo account to test.

Start by reading `docs/HANDOFF-SESSION2.md`, then run the identity-bug diagnostic
and report what the three lines return before making changes.
