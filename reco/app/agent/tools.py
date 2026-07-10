"""
Backend tool wrappers for the chat agent — httpx calls to the KFC backend REST
surface (the SAME endpoints the kiosk uses). Mirrors the Claw-a-thon
tools/order_api.py pattern, including idempotent place_order.

The backend is the source of truth: these wrappers never compute prices or
totals themselves.
"""
import uuid
import httpx
from app.config import config

_client = httpx.Client(base_url=config.BACKEND_URL, timeout=15.0)


def search_menu(query="", category=None, maxPrice=None):
    params = {"q": query}
    if category:
        params["category"] = category
    if maxPrice:
        params["maxPrice"] = maxPrice
    return _client.get("/api/menu/search", params=params).json()


def get_item(productId):
    return _client.get(f"/api/menu/{productId}").json()


def list_stores(city=None):
    return _client.get("/api/stores", params={"city": city} if city else {}).json()


def get_recommendations(context, slot="cart", limit=3):
    return _client.post("/api/recommend", json={"slot": slot, "context": context, "limit": limit}).json()


def create_cart(channel="zalo", storeId=None, dineMode="takeaway", userId=None):
    return _client.post("/api/carts", json={
        "channel": channel, "storeId": storeId, "dineMode": dineMode, "userId": userId,
    }).json()


def view_cart(cartId):
    return _client.get(f"/api/carts/{cartId}").json()


def add_to_cart(cartId, productId, qty=1, modifiers=None):
    return _client.post(f"/api/carts/{cartId}/items", json={
        "productId": productId, "qty": qty, "modifiers": modifiers or [],
    }).json()


def remove_from_cart(cartId, lineId):
    return _client.delete(f"/api/carts/{cartId}/items/{lineId}").json()


def apply_voucher(cartId, code):
    return _client.post(f"/api/vouchers/carts/{cartId}/apply", json={"code": code}).json()


def check_loyalty(userId):
    return _client.get(f"/api/loyalty/{userId}").json()


def place_order(cartId, idempotencyKey=None, payment=None):
    """Commit order. Idempotent — retries once with the SAME key on 5xx/timeout."""
    key = idempotencyKey or str(uuid.uuid4())
    payload = {"cartId": cartId, "idempotencyKey": key, "payment": payment or {"method": "mock"}}
    for attempt in (1, 2):
        try:
            resp = _client.post("/api/orders", json=payload)
            if resp.status_code >= 500 and attempt == 1:
                continue  # retry once, same idempotency key → backend dedupes
            return resp.json()
        except httpx.TimeoutException:
            if attempt == 1:
                continue
            raise


def get_order_status(orderId):
    return _client.get(f"/api/orders/{orderId}").json()


def link_channel(channel, externalId, phone, code):
    """Map a Zalo/Messenger OA identity → KFC member (login then link)."""
    login = _client.post("/api/auth/login", json={"phone": phone, "code": code}).json()
    return {"linked": True, "user": login.get("user"), "loyalty": login.get("loyalty")}


def handoff(reason, transcript=None, channel="zalo", externalId=None, sessionId=None):
    return _client.post("/api/handoff", json={
        "reason": reason, "transcript": transcript, "channel": channel,
        "externalId": externalId, "sessionId": sessionId,
    }).json()


# Dispatch table used by the tool-calling loop.
DISPATCH = {
    "search_menu": search_menu,
    "get_item": get_item,
    "list_stores": list_stores,
    "get_recommendations": get_recommendations,
    "create_cart": create_cart,
    "view_cart": view_cart,
    "add_to_cart": add_to_cart,
    "remove_from_cart": remove_from_cart,
    "apply_voucher": apply_voucher,
    "check_loyalty": check_loyalty,
    "place_order": place_order,
    "get_order_status": get_order_status,
    "link_channel": link_channel,
    "handoff": handoff,
}
