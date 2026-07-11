"""
Tool-calling orchestration loop for the KFC chat ordering agent.

Thin orchestrator: the LLM decides WHICH tool to call; tools.py calls the
backend, which owns all state and validation. Bounded iterations to avoid loops.
Channel-agnostic by design — the web harness, Zalo OA webhook, and Messenger
all feed the same chat() entrypoint; only the transport differs.

LLM access goes through app.llm_client (raw httpx POST, no SDK) — the flow
proven on this machine by random-bullshlt's reportGenerator.js.

Session persistence: cartId and userId survive across turns (Mongo-backed),
are injected into tool args when the model omits them, and the cart reference
is cleared after a successful place_order so the next order starts fresh.
"""
import json
import re
from app.agent.registry import TOOL_DEFINITIONS, SYSTEM_PROMPT
from app.agent.tools import DISPATCH, attach_user_to_cart, resolve_identity
from app.agent.session import load_session, save_session
from app import llm_client

MAX_TOOL_ROUNDS = 6
NEEDS_CART = {"add_to_cart", "view_cart", "remove_from_cart", "apply_voucher", "place_order"}
# Tools that CANNOT work without a linked member → hard prompt for the phone.
MEMBER_REQUIRED = {"check_loyalty", "my_orders", "reorder_last"}

# Strip leaked reasoning/tool-XML from MaaS models (minimax etc.) — ported
# from random-bullshlt agent/llm.py sanitize_response().
_SANITIZE_RES = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"</?(?:invoke|minimax:tool_call|parameter)[^>]*>", re.IGNORECASE),
]


def _sanitize(text):
    for rx in _SANITIZE_RES:
        text = rx.sub("", text or "")
    return text.strip()


def _run_tool(name, args, ctx):
    """Execute a tool, injecting session context (cartId/userId/channel) the model omitted."""
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}

    # ── Deterministic login gate ──────────────────────────────────────────────
    # Tie the "please link your phone" ask to INTENT rather than nagging every
    # turn. The model only reaches for these tools when the user's message is
    # about member data or confirming an order, so intercepting them here re-asks
    # at exactly the right moments — no keyword guessing.
    if not ctx.get("userId"):
        if name in MEMBER_REQUIRED:
            ctx["linkAsked"] = True
            return {"needs_link": True,
                    "message": "Tính năng này cần liên kết thành viên. Hãy hỏi SỐ ĐIỆN THOẠI "
                               "của khách, rồi gọi link_channel(phone=...). Không cần mã OTP."}
        if name == "place_order" and not ctx.get("orderLinkPitched"):
            # Ordering stays anonymous-friendly: pitch linking ONCE per order, but
            # let the customer decline and still check out (they'll re-call place_order).
            ctx["orderLinkPitched"] = True
            ctx["linkAsked"] = True
            return {"needs_link": "optional",
                    "message": "Trước khi chốt đơn: mời khách để lại SỐ ĐIỆN THOẠI để tích điểm "
                               "và nhận ưu đãi thành viên (gọi link_channel). Nếu khách KHÔNG "
                               "muốn, gọi lại place_order để chốt đơn ẩn danh."}

    if name in NEEDS_CART and not args.get("cartId") and ctx.get("cartId"):
        args["cartId"] = ctx["cartId"]
    if name == "create_cart":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        if ctx.get("userId"):
            args.setdefault("userId", ctx["userId"])
    if name in ("check_loyalty", "my_orders", "reorder_last") and not args.get("userId") and ctx.get("userId"):
        args["userId"] = ctx["userId"]
    if name == "reorder_last":
        args.setdefault("channel", ctx.get("channel", "zalo"))
    if name == "get_recommendations":
        c = args.get("context") or {}
        c.setdefault("cartId", ctx.get("cartId"))
        c.setdefault("userId", ctx.get("userId"))
        c.setdefault("channel", ctx.get("channel", "zalo"))
        args["context"] = c
    if name == "link_channel":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        args.setdefault("externalId", ctx.get("externalId") or ctx.get("sessionId"))
    if name == "handoff":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        args.setdefault("externalId", ctx.get("externalId"))
        args.setdefault("sessionId", ctx.get("sessionId"))
    if name == "place_order":
        # QR payment needs the OA-scoped id so the pay webhook can push back.
        args.setdefault("externalId", ctx.get("externalId"))
    try:
        return fn(**args)
    except Exception as e:
        return {"error": "tool_failed", "detail": str(e)[:200]}


def _track(name, result, ctx):
    """Update session context from tool results."""
    if not isinstance(result, dict):
        return
    if name in ("create_cart", "reorder_last") and result.get("cartId"):
        ctx["cartId"] = str(result["cartId"])
    if name == "link_channel" and result.get("linked"):
        uid = (result.get("user") or {}).get("id")
        if uid:
            ctx["userId"] = str(uid)
            # Mid-order login: tie the open cart to the member so the order
            # earns points AND feeds their personalization history.
            if ctx.get("cartId"):
                try:
                    attach_user_to_cart(ctx["cartId"], ctx["userId"])
                except Exception:
                    pass
    if name == "place_order" and result.get("orderId") and not result.get("error"):
        ctx["cartId"] = ""  # cart is committed — next order starts a new one
        ctx["orderLinkPitched"] = False  # fresh order → pitch linking again if still anon
    # QR checkout produced a scannable image → transport sends it after the reply.
    if result.get("qrImageUrl"):
        ctx["pendingImageUrl"] = result["qrImageUrl"]


def _finish(session_id, messages, ctx, reply, trace):
    save_session(
        session_id, messages,
        state={"userId": ctx.get("userId"),
               "linkAsked": bool(ctx.get("linkAsked")),
               "orderLinkPitched": bool(ctx.get("orderLinkPitched"))},
        cart_id=ctx.get("cartId"),
    )
    return {"reply": reply, "toolTrace": trace,
            "cartId": ctx.get("cartId") or None, "userId": ctx.get("userId"),
            "imageUrl": ctx.get("pendingImageUrl")}


def chat(session_id, user_message, ctx=None):
    """
    Run one user turn through the agent. Returns {reply, toolTrace, cartId, userId}.
    `ctx` carries channel/externalId/userId for tool injection; cartId/userId
    are restored from the persisted session when not supplied.
    """
    ctx = ctx or {}
    ctx["sessionId"] = session_id

    session = load_session(session_id)
    state = session.get("state") or {}
    if not ctx.get("cartId"):
        ctx["cartId"] = session.get("cartId") or None
    if not ctx.get("userId"):
        ctx["userId"] = state.get("userId")
    ctx["linkAsked"] = ctx.get("linkAsked") or state.get("linkAsked", False)
    ctx["orderLinkPitched"] = ctx.get("orderLinkPitched") or state.get("orderLinkPitched", False)

    # Durable identity: resolve the OA-scoped id (zaloIdByOA) against
    # channel_identities. Linked → member recognized across sessions without
    # re-login; unlinked → the agent pitches linking ONCE (see system note).
    identity = None
    if not ctx.get("userId") and ctx.get("externalId"):
        identity = resolve_identity(ctx.get("channel", "zalo"), ctx["externalId"])
        if identity.get("linked"):
            ctx["userId"] = str(identity["user"]["id"])

    messages = session.get("messages") or []
    if not messages:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        if identity is not None and identity.get("linked"):
            u, loy = identity["user"], identity.get("loyalty") or {}
            messages.append({"role": "system", "content":
                f"[HỆ THỐNG] Khách đã liên kết: {u.get('name')} (hạng {u.get('tier')}, "
                f"{loy.get('pointsBalance', 0)} điểm). Chào theo tên và có thể chủ động "
                f"gợi ý 'đặt lại đơn quen thuộc' (reorder_last)."})

    # No proactive login pitch — the agent only asks for a phone number when the
    # customer's intent needs it (member tools → needs_link; place_order → optional
    # pitch), handled by the gate in _run_tool. Keeps the greeting natural.
    messages.append({"role": "user", "content": user_message})

    if not llm_client.available():
        reply = "(Agent chưa cấu hình OPENAI_API_KEY — đây là bản khung. Backend + tools đã sẵn sàng.)"
        messages.append({"role": "assistant", "content": reply})
        return _finish(session_id, messages, ctx, reply, [])

    trace = []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            msg = llm_client.chat(messages, tools=TOOL_DEFINITIONS, temperature=0.3)
        except Exception as e:
            # LLM unreachable (network/key/model) must never 500 the channel.
            print(f"[agent] LLM call failed: {type(e).__name__}: {str(e)[:300]}")
            return _finish(session_id, messages, ctx,
                           "Xin lỗi, trợ lý AI đang tạm mất kết nối. Bạn thử lại sau ít phút nhé! 🙏",
                           trace)
        messages.append(msg)  # already a plain dict

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return _finish(session_id, messages, ctx, _sanitize(msg.get("content")), trace)

        # Execute each requested tool and feed results back.
        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "")
            try:
                args = json.loads(tc.get("function", {}).get("arguments") or "{}")
            except Exception:
                args = {}
            result = _run_tool(name, args, ctx)
            _track(name, result, ctx)
            trace.append({"tool": name, "args": args})
            messages.append({
                "role": "tool", "tool_call_id": tc.get("id"),
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Ran out of rounds — return a safe fallback.
    return _finish(session_id, messages, ctx,
                   "Xin lỗi, mình cần thêm thông tin để tiếp tục.", trace)
