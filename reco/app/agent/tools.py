"""
Backend tool wrappers for the chat agent — httpx calls to the KFC backend REST
surface (the SAME endpoints the kiosk uses). Mirrors the Claw-a-thon
tools/order_api.py pattern, including idempotent place_order.

The backend is the source of truth: these wrappers never compute prices or
totals themselves. Responses are COMPACTED before returning to the LLM — full
product/cart docs (descriptions, image URLs, timestamps) would waste tokens
and drown the model in noise.
"""
import secrets
import time
import uuid
import httpx
from app.config import config
from app.db import get_db

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
        "deliveryAddress": cart.get("deliveryAddress"),
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


def list_categories():
    """Danh sách các NHÓM món (category) để trình bày menu theo nhóm trước khi
    tìm món cụ thể. Powers 'xem menu' / 'KFC có món gì'."""
    data = _client.get("/api/menu/categories").json()
    return {"categories": data.get("categories") or []}


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


def set_delivery(cartId, address, name=None, phone=None):
    """Lưu địa chỉ giao hàng (và tên/SĐT người nhận) vào giỏ. Đặt dineMode=delivery."""
    body = {"deliveryAddress": address}
    if name:
        body["contactName"] = name
    if phone:
        body["contactPhone"] = phone
    return _compact_cart(_client.patch(f"/api/carts/{cartId}", json=body).json())


def place_order(cartId, idempotencyKey=None, payment=None, externalId=None):
    """Commit order. Idempotent — retries once with the SAME key on 5xx/timeout.
    For payment.method == 'qr' the order is created PENDING and we mint a payment
    token + QR image URL (served by reco) so the customer can scan to pay."""
    key = idempotencyKey or str(uuid.uuid4())
    payment = payment or {"method": "mock"}
    payload = {"cartId": cartId, "idempotencyKey": key, "payment": payment}
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
    out = {
        "orderId": str(order.get("_id", "")),
        "status": order.get("status"),
        "total": (order.get("totals") or {}).get("grandTotal"),
        "pointsEarned": data.get("pointsEarned", order.get("pointsEarned", 0)),
        "deduped": data.get("deduped", False),
        "paymentMethod": (order.get("payment") or {}).get("method"),
        "paymentStatus": (order.get("payment") or {}).get("status"),
    }
    # QR flow: create a payment token + QR image the transport will send.
    if payment.get("method") == "qr" and out["orderId"]:
        token = secrets.token_urlsafe(16)
        get_db().zalo_payments.insert_one({
            "_id": token, "orderId": out["orderId"], "externalId": externalId,
            "amount": out["total"], "status": "pending", "ts": time.time(),
        })
        base = config.PUBLIC_BASE_URL.rstrip("/")
        out["payUrl"] = f"{base}/zalo/pay?token={token}"
        out["qrImageUrl"] = f"{base}/zalo/pay/qr?token={token}"
        out["paymentPending"] = True
    return out


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


def resolve_identity(channel, externalId):
    """Durable identity lookup: is this OA-scoped id linked to a member?
    Called by the agent loop on session start — NOT exposed to the LLM."""
    try:
        return _client.get(f"/api/channel/resolve/{channel}/{externalId}").json()
    except Exception:
        return {"linked": False}


def link_channel(channel, externalId, phone, code=None):
    """Map a Zalo/Messenger OA identity → KFC member by phone number (no OTP).
    Persists the mapping in channel_identities so every FUTURE chat auto-recognizes
    this user. `code` is accepted for backward compatibility but ignored."""
    data = _client.post("/api/channel/link", json={
        "channel": channel, "externalId": externalId, "phone": phone,
    }).json()
    return {"linked": bool(data.get("linked")), "user": data.get("user"), "loyalty": data.get("loyalty")}


def attach_user_to_cart(cartId, userId):
    """After link_channel mid-order: tie the open cart to the member."""
    return _compact_cart(_client.patch(f"/api/carts/{cartId}", json={"userId": userId}).json())


def list_vouchers():
    """Active promo codes — powers 'có khuyến mãi gì không?'."""
    data = _client.get("/api/vouchers").json()
    return {"vouchers": [{
        "code": v.get("code"), "description": v.get("description"),
        "type": v.get("type"), "value": v.get("value"),
        "minOrder": (v.get("conditions") or {}).get("minOrder", 0),
    } for v in (data.get("vouchers") or [])]}


def my_orders(userId, limit=5):
    """Member's recent orders — powers 'đơn của tôi đâu/tôi đã đặt gì?'."""
    return _client.get(f"/api/orders/user/{userId}", params={"limit": limit}).json()


def reorder_last(userId, dineMode="dine_in", channel="zalo"):
    """One-shot reorder: build a NEW cart from the member's last order (falls
    back to their purchase history). Returns the compact cart for read-back."""
    basket = _client.get(f"/api/orders/user/{userId}/last-basket").json()
    if not basket.get("found"):
        return {"error": "no_history", "detail": "Thành viên chưa có đơn/lịch sử để đặt lại."}
    cart = _client.post("/api/carts", json={
        "channel": channel, "dineMode": dineMode, "userId": userId,
    }).json()
    cart_id = str(cart.get("_id"))
    for item in basket["items"]:
        _client.post(f"/api/carts/{cart_id}/items", json={
            "productId": item["productId"], "qty": item.get("qty", 1),
        })
    final = _client.get(f"/api/carts/{cart_id}").json()
    out = _compact_cart(final)
    if isinstance(out, dict):
        out["source"] = basket.get("source")  # "order" (live) vs "transaction" (history)
    return out


def handoff(reason, transcript=None, channel="zalo", externalId=None, sessionId=None):
    return _client.post("/api/handoff", json={
        "reason": reason, "transcript": transcript, "channel": channel,
        "externalId": externalId, "sessionId": sessionId,
    }).json()


# Dispatch table used by the tool-calling loop.
DISPATCH = {
    "search_menu": search_menu,
    "get_item": get_item,
    "list_categories": list_categories,
    "list_stores": list_stores,
    "get_recommendations": get_recommendations,
    "create_cart": create_cart,
    "view_cart": view_cart,
    "add_to_cart": add_to_cart,
    "remove_from_cart": remove_from_cart,
    "apply_voucher": apply_voucher,
    "check_loyalty": check_loyalty,
    "set_delivery": set_delivery,
    "place_order": place_order,
    "get_order_status": get_order_status,
    "list_vouchers": list_vouchers,
    "my_orders": my_orders,
    "reorder_last": reorder_last,
    "link_channel": link_channel,
    "handoff": handoff,
}
