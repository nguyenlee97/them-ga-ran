"""
Zalo OA transport for the P4 chat agent.

Everything Zalo-specific lives here; the agent loop (loop.chat) stays
channel-agnostic. Three responsibilities:

  1. Token manager  — access tokens live ~1h and refresh tokens ROTATE on every
     use, so we persist both in Mongo (`zalo_tokens`), seed from env on first
     boot, and refresh via OAuth v4 with a safety margin (or on a token error).
  2. Signature      — verify the `X-ZEvent-Signature` MAC so only Zalo can post
     to our webhook.
  3. Send           — reply to the user via the OA "customer service" message API
     (v3.0), auto-refreshing + retrying once on a token error.

Docs: https://developers.zalo.me/docs/official-account
"""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.config import config
from app.db import get_db

# Zalo returns error==0 on success; these negative codes mean the access token
# is stale/invalid → refresh once and retry.
_TOKEN_ERRORS = {-124, -216, -32003, -32000}
_REFRESH_MARGIN_S = 300  # refresh 5 min before expiry
_MAX_TEXT = 2000         # CS text message hard cap (chars)

_http = httpx.Client(timeout=15.0)


def _coll():
    return get_db().zalo_tokens


# ── token manager ────────────────────────────────────────────────────────────

def _load_tokens():
    """Return the persisted token doc, seeding it from env on first boot."""
    doc = _coll().find_one({"_id": "oa"})
    if not doc:
        doc = {
            "_id": "oa",
            "access_token": config.ZALO_ACCESS_TOKEN,
            "refresh_token": config.ZALO_REFRESH_TOKEN,
            # expiry unknown for the seed token → let the first API call discover
            # staleness and refresh reactively.
            "expires_at": 0,
            "updated_at": time.time(),
        }
        _coll().insert_one(doc)
    return doc


def _refresh(doc):
    """Exchange the (rotating) refresh token for a fresh access token.

    OAuth v4: POST form-urlencoded, app secret goes in the `secret_key` header.
    The response carries a NEW refresh_token that MUST replace the old one.
    """
    refresh_token = doc.get("refresh_token") or config.ZALO_REFRESH_TOKEN
    if not refresh_token:
        raise RuntimeError("no Zalo refresh_token configured")
    resp = _http.post(
        config.ZALO_OAUTH_URL,
        headers={
            "secret_key": config.ZALO_APP_SECRET,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "refresh_token": refresh_token,
            "app_id": config.ZALO_APP_ID,
            "grant_type": "refresh_token",
        },
    )
    data = resp.json()
    access = data.get("access_token")
    if not access:
        raise RuntimeError(f"Zalo token refresh failed: {data}")
    new_doc = {
        "access_token": access,
        # fall back to the old RT if Zalo omits a new one (shouldn't happen)
        "refresh_token": data.get("refresh_token") or refresh_token,
        "expires_at": time.time() + int(data.get("expires_in") or 3600),
        "updated_at": time.time(),
    }
    _coll().update_one({"_id": "oa"}, {"$set": new_doc}, upsert=True)
    print("[zalo] access token refreshed")
    return {**doc, **new_doc}


def get_access_token(force_refresh=False):
    doc = _load_tokens()
    expires_at = doc.get("expires_at") or 0
    if force_refresh or (expires_at and time.time() > expires_at - _REFRESH_MARGIN_S):
        doc = _refresh(doc)
    return doc.get("access_token")


# ── OAuth consent (PKCE) — obtain a fresh token pair via admin approval ───────
# Flow: admin opens /zalo/oauth/login → we redirect to Zalo's permission page →
# admin approves → Zalo redirects to /zalo/oauth/callback?code&state → we swap the
# code for access+refresh tokens and persist them. Only needed to (re)seed tokens;
# day-to-day the refresh grant keeps them alive.

def _oauth_coll():
    return get_db().zalo_oauth


def _new_pkce():
    """S256 PKCE: random verifier + base64url(sha256(verifier)) challenge."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def start_consent() -> str:
    """Persist a fresh PKCE verifier keyed by state; return Zalo's permission URL."""
    verifier, challenge = _new_pkce()
    state = secrets.token_urlsafe(16)
    _oauth_coll().update_one(
        {"_id": state}, {"$set": {"code_verifier": verifier, "ts": time.time()}}, upsert=True
    )
    q = urlencode({
        "app_id": config.ZALO_APP_ID,
        "redirect_uri": config.ZALO_REDIRECT_URI,
        "code_challenge": challenge,
        "state": state,
    })
    return f"{config.ZALO_OAUTH_PERMISSION_URL}?{q}"


def finish_consent(code: str, state: str) -> dict:
    """Exchange the auth code (with the stored verifier) for a token pair; persist."""
    doc = _oauth_coll().find_one({"_id": state})
    if not doc:
        raise RuntimeError("unknown or expired state — restart at /zalo/oauth/login")
    resp = _http.post(
        config.ZALO_OAUTH_URL,
        headers={"secret_key": config.ZALO_APP_SECRET,
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"code": code, "app_id": config.ZALO_APP_ID,
              "grant_type": "authorization_code", "code_verifier": doc["code_verifier"]},
    )
    data = resp.json()
    access = data.get("access_token")
    if not access:
        raise RuntimeError(f"token exchange failed: {data}")
    _coll().update_one({"_id": "oa"}, {"$set": {
        "access_token": access,
        "refresh_token": data.get("refresh_token"),
        "expires_at": time.time() + int(data.get("expires_in") or 3600),
        "updated_at": time.time(),
    }}, upsert=True)
    _oauth_coll().delete_one({"_id": state})
    print("[zalo] OAuth consent complete — token pair stored")
    return data


# ── signature verification ───────────────────────────────────────────────────

def verify_signature(raw_body: bytes, timestamp: str, mac_header: str) -> bool:
    """Zalo signs each webhook: mac = SHA256(appId + data + timestamp + OASecret).

    `data` is the raw request body exactly as received; the header arrives as
    "mac=<hexdigest>". If no OA secret is configured we skip verification (dev).
    """
    if not config.ZALO_OA_SECRET:
        return True
    if not mac_header:
        return False
    expected = hashlib.sha256(
        (config.ZALO_APP_ID + raw_body.decode("utf-8") + str(timestamp) + config.ZALO_OA_SECRET).encode("utf-8")
    ).hexdigest()
    got = mac_header.split("mac=", 1)[-1].strip()
    return _consteq(expected, got)


def _consteq(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    r = 0
    for x, y in zip(a, b):
        r |= ord(x) ^ ord(y)
    return r == 0


# ── event parsing ────────────────────────────────────────────────────────────

def parse_event(body: dict):
    """Normalise a Zalo webhook payload → (event_name, user_id, text).

    We only act on `user_send_text`; everything else (follow, image, sticker…)
    returns text=None so the caller can ignore or branch.
    """
    event = body.get("event_name")
    user_id = (body.get("sender") or {}).get("id")
    text = None
    if event == "user_send_text":
        text = (body.get("message") or {}).get("text")
    return event, user_id, text


# ── send ─────────────────────────────────────────────────────────────────────

def send_text(user_id: str, text: str) -> dict:
    """Send a CS text message, refreshing + retrying once on a token error."""
    if not text:
        return {"error": "empty_text"}
    payload = {"recipient": {"user_id": str(user_id)}, "message": {"text": text[:_MAX_TEXT]}}
    url = f"{config.ZALO_OA_API_URL}/v3.0/oa/message/cs"

    for attempt in (1, 2):
        token = get_access_token(force_refresh=(attempt == 2))
        resp = _http.post(url, headers={"access_token": token, "Content-Type": "application/json"}, json=payload)
        try:
            data = resp.json()
        except Exception:
            data = {"error": -1, "message": resp.text[:200]}
        if data.get("error") in _TOKEN_ERRORS and attempt == 1:
            print(f"[zalo] token error {data.get('error')} → refreshing and retrying")
            continue
        if data.get("error") not in (0, None):
            print(f"[zalo] send failed: {data}")
        return data
    return data


def send_image(user_id: str, image_url: str) -> dict:
    """Send an image (e.g., the payment QR) via the CS message media attachment.
    Same token refresh + single retry as send_text."""
    if not image_url:
        return {"error": "empty_image"}
    payload = {
        "recipient": {"user_id": str(user_id)},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "media",
            "elements": [{"media_type": "image", "url": image_url}],
        }}},
    }
    url = f"{config.ZALO_OA_API_URL}/v3.0/oa/message/cs"
    for attempt in (1, 2):
        token = get_access_token(force_refresh=(attempt == 2))
        resp = _http.post(url, headers={"access_token": token, "Content-Type": "application/json"}, json=payload)
        try:
            data = resp.json()
        except Exception:
            data = {"error": -1, "message": resp.text[:200]}
        if data.get("error") in _TOKEN_ERRORS and attempt == 1:
            continue
        if data.get("error") not in (0, None):
            print(f"[zalo] send_image failed: {data}")
        return data
    return data
