"""
Backend tool wrappers for the chat agent — httpx calls to the KFC backend REST
surface (the SAME endpoints the kiosk uses). Mirrors the Claw-a-thon
tools/order_api.py pattern, including idempotent place_order.

The backend is the source of truth: these wrappers never compute prices or
totals themselves. Responses are COMPACTED before returning to the LLM — full
product/cart docs (descriptions, image URLs, timestamps) would waste tokens
and drown the model in noise.
"""
import uuid
import httpx
from app.config import config

_client = httpx.Client(base_url=config.BACKEND_URL, timeout=15.0)


# ── response compaction ──────────────────────────────────────────────────────

def _compact_product(p):
    return {
        "productId": str(p.get("_id", "")),
        "sku": p.get("sku"),
        "name": p.get("name_vi"),
        "price": p.get("price"),
        "category": p.get("category"),
        "isCombo": bool(p.get("isCombo")),
    }


def _compact_cart(cart):
    if not isinstance(cart, dict) or not cart.get("_id"):
        return cart  # error payloads pass through untouched
    return {
        "cartId": str(cart["_id"]),
        "status": cart.get("status"),
        "dineMode": cart.get("dineMode"),
        "items": [{
            "lineId": i.get("lineId"),
            "name": i.get("name_vi"),
            "qty": i.get("qty"),
            "unitPrice": i.get("unitPrice"),
            "lineTotal": i.get("lineTotal"),
        } for i in cart.get("items", [])],
        "vouchers": cart.get("appliedVouchers", []),
        "totals": cart.get("totals"),
    }


# ── tools ────────────────────────────────────────────────────────────────────

def search_menu(query="", category=None, maxPrice=None):
    params = {"q": query}
    if category:
        params["category"] = category
    if maxPrice:
        params["maxPrice"] = maxPrice
    data = _client.get("/api/menu/search", params=params).json()
    items = data.get("items") or []
    return {"count": data.get("count", len(items)), "items": [_compact_product(p) for p in items[:12]]}


def get_item(productId):
    return _compact_product(_client.get(f"/api/menu/{productId}").json())


def list_stores(city=None):
    data = _client.get("/api/stores", params={"city": city} if city else {}).json()
    stores = data.get("stores") or data.get("items") or (data if isinstance(data, list) else [])
    return {"stores": [{
        "storeId": str(s.get("_id", "")), "name": s.get("name"),
        "address": s.get("address"), "city": s.get("city"),
    } for s in stores[:10]]}


def get_recommendations(context, slot="cart", limit=3):
    data = _client.post("/api/recommend", json={"slot": slot, "context": context, "limit": limit}).json()
    out = {"recommendations": [{
        "productId": r.get("productId"), "sku": r.get("sku"), "name": r.get("name"),
        "price": r.get("price"), "reason": r.get("reason"), "copy": r.get("copy"),
    } for r in (data.get("recommendations") or [])]}
    cu = data.get("comboUpsell")
    if cu:
        out["comboUpsell"] = {
            "sku": cu.get("sku"), "name": cu.get("name"), "price": cu.get("price"),
            "priceDelta": cu.get("priceDelta"), "copy": cu.get("copy"),
        }
    return out


def create_cart(channel="zalo", storeId=None, dineMode="takeaway", userId=None):
    return _compact_cart(_client.post("/api/carts", json={
        "channel": channel, "storeId": storeId, "dineMode": dineMode, "userId": userId,
    }).json())


def view_cart(cartId):
    return _compact_cart(_client.get(f"/api/carts/{cartId}").json())


def add_to_cart(cartId, productId, qty=1, modifiers=None):
    return _compact_cart(_client.post(f"/api/carts/{cartId}/items", json={
        "productId": productId, "qty": qty, "modifiers": modifiers or [],
    }).json())


def remove_from_cart(cartId, lineId):
    return _compact_cart(_client.delete(f"/api/carts/{cartId}/items/{lineId}").json())


def apply_voucher(cartId, code):
    data = _client.post(f"/api/vouchers/carts/{cartId}/apply", json={"code": code}).json()
    return {
        "applied": data.get("applied"), "discount": data.get("discount"),
        "reason": data.get("reason"), "cart": _compact_cart(data.get("cart")),
    }


def check_loyalty(userId):
    return _client.get(f"/api/loyalty/{userId}").json()


def place_order(cartId, idempotencyKey=None, payment=None):
    """Commit order. Idempotent — retries once with the SAME key on 5xx/timeout."""
    key = idempotencyKey or str(uuid.uuid4())
    payload = {"cartId": cartId, "idempotencyKey": key, "payment": payment or {"method": "mock"}}
    data = None
    for attempt in (1, 2):
        try:
            resp = _client.post("/api/orders", json=payload)
            if resp.status_code >= 500 and attempt == 1:
                continue  # retry once, same idempotency key → backend dedupes
            data = resp.json()
            break
        except httpx.TimeoutException:
            if attempt == 1:
                continue
            raise
    order = (data or {}).get("order")
    if not order:
        return data  # error payload
    return {
        "orderId": str(order.get("_id", "")),
        "status": order.get("status"),
        "total": (order.get("totals") or {}).get("grandTotal"),
        "pointsEarned": data.get("pointsEarned", order.get("pointsEarned", 0)),
        "deduped": data.get("deduped", False),
    }


def get_order_status(orderId):
    data = _client.get(f"/api/orders/{orderId}").json()
    order = data.get("order") or data
    if not isinstance(order, dict) or not order.get("_id"):
        return data
    return {
        "orderId": str(order["_id"]), "status": order.get("status"),
        "total": (order.get("totals") or {}).get("grandTotal"),
        "placedAt": str(order.get("placedAt")),
    }


def link_channel(channel, externalId, phone, code):
    """Map a Zalo/Messenger OA identity → KFC member (login then link)."""
    login = _client.post("/api/auth/login", json={"phone": phone, "code": code}).json()
    return {"linked": bool(login.get("user")), "user": login.get("user"), "loyalty": login.get("loyalty")}


def attach_user_to_cart(cartId, userId):
    """After link_channel mid-order: tie the open cart to the member."""
    return _compact_cart(_client.patch(f"/api/carts/{cartId}", json={"userId": userId}).json())


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
