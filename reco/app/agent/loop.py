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
import unicodedata
from datetime import datetime, timezone

from app.agent.registry import TOOL_DEFINITIONS, SYSTEM_PROMPT
from app.agent.tools import DISPATCH, attach_user_to_cart, resolve_identity
from app.agent.session import load_session, save_session
from app import llm_client
from app.config import config

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
_INTERNAL_LINE_RE = re.compile(
    r"\b(?:backend|api|tool|database|mongodb)\b|cơ sở dữ liệu",
    re.IGNORECASE,
)


def _sanitize(text):
    for rx in _SANITIZE_RES:
        text = rx.sub("", text or "")
    # Defense in depth: implementation details must never leak into Zalo copy.
    # The prompt prevents this normally; this catches an occasional model slip.
    lines = []
    replaced_internal = False
    for line in text.splitlines():
        if _INTERNAL_LINE_RE.search(line):
            if not replaced_internal:
                lines.append("Mình chưa có đủ thông tin để trả lời chính xác nội dung này ạ.")
                replaced_internal = True
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _as_utc(value):
    """Normalize Mongo/Python datetimes for idle-window comparisons."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _conversation_expired(session, now=None):
    """A Zalo id is durable; its current conversation expires after inactivity."""
    if not session.get("messages"):
        return False
    last = _as_utc(session.get("lastActivityAt") or session.get("updatedAt"))
    # Existing session documents predate activity metadata. Start them cleanly
    # once after deploy instead of replaying an unbounded legacy transcript.
    if last is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - last).total_seconds() > config.CHAT_IDLE_TIMEOUT_SECONDS


def _bounded_messages(messages):
    """Keep the base system prompt plus recent complete user turns.

    Cutting only at a user boundary prevents orphaned `tool` messages, which
    OpenAI-compatible APIs reject when their preceding tool_call was trimmed.
    """
    # Always use the currently deployed prompt. Persisted sessions may contain
    # an older prompt version and should pick up tone/safety fixes immediately.
    system = {"role": "system", "content": SYSTEM_PROMPT}
    body = [m for m in messages if m.get("role") != "system"]
    limit = max(4, config.CHAT_CONTEXT_MESSAGES)
    if len(body) <= limit:
        return [system, *body]

    user_starts = [i for i, m in enumerate(body) if m.get("role") == "user"]
    fitting = [i for i in user_starts if len(body) - i <= limit]
    if fitting:
        start = min(fitting)  # widest suffix that stays under the cap
    elif user_starts:
        start = user_starts[-1]  # one unusually tool-heavy turn stays intact
    else:
        start = max(0, len(body) - limit)
    return [system, *body[start:]]


def _extract_phone(text):
    """Extract a VN phone only while a deterministic link continuation is pending."""
    for raw in re.findall(r"(?:\+?84|0)(?:[ .-]*\d){8,10}", text or ""):
        phone = _normalize_phone(raw)
        if phone:
            return phone
    return None


def _normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits if 9 <= len(digits) <= 11 else None


def _mask_phone(phone):
    phone = _normalize_phone(phone)
    if not phone or len(phone) < 7:
        return "SĐT đã liên kết"
    return f"{phone[:4]}***{phone[-3:]}"


def _plain_vi(text):
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _other_member_phone_reply(user_message, ctx):
    """Block cross-member lookups before the LLM can produce a misleading reply."""
    if not ctx.get("userId"):
        return None
    supplied = _extract_phone(user_message)
    linked = _normalize_phone((ctx.get("identityUser") or {}).get("phone"))
    if not supplied or not linked or supplied == linked:
        return None
    personal_intent = re.search(
        r"\b(kiem tra|lich su|don hang cu|don cu|diem|tai khoan|thanh vien|dat lai)\b",
        _plain_vi(user_message),
    )
    if not personal_intent:
        return None  # likely a per-order delivery contact number
    return (
        f"À, Zalo này đang liên kết với SĐT thành viên {_mask_phone(linked)}, nên mình "
        "chỉ xem được điểm và đơn cũ của tài khoản đó thôi. Mình không thể tra cứu "
        f"SĐT {_mask_phone(supplied)} nhé.\n\n"
        "Riêng lúc đặt món, bạn vẫn dùng SĐT nhận hàng khác bình thường — số nhận "
        "hàng không làm đổi tài khoản thành viên. Nếu cần đổi tài khoản đã liên kết, "
        "mình sẽ chuyển bạn đến nhân viên hỗ trợ."
    )


def _runtime_context(ctx, notes=None):
    """Fresh backend identity is injected every turn but never persisted as chat."""
    user = ctx.get("identityUser") or {}
    if ctx.get("userId"):
        identity = (
            f"[TRẠNG THÁI HIỆN TẠI] Khách ĐÃ liên kết thành viên: "
            f"userId={ctx['userId']}, tên={user.get('name') or 'Thành Viên KFC'}, "
            f"hạng={user.get('tier') or 'member'}, SĐT thành viên={user.get('phone') or 'không rõ'}. "
            "KHÔNG hỏi lại SĐT để xác thực và KHÔNG đổi sang thành viên khác. "
            "Khi khách hỏi tài khoản/điểm/lịch sử, dùng đúng userId này. "
            "SĐT người nhận hàng có thể khác và chỉ dùng cho đơn giao hàng."
        )
    else:
        identity = "[TRẠNG THÁI HIỆN TẠI] Khách chưa liên kết thành viên."
    extra = "\n".join(notes or [])
    return {"role": "system", "content": identity + (f"\n{extra}" if extra else "")}


def _messages_for_llm(messages, ctx, notes=None):
    bounded = _bounded_messages(messages)
    return [bounded[0], _runtime_context(ctx, notes), *bounded[1:]]


def _run_tool(name, args, ctx):
    """Execute a tool, injecting session context (cartId/userId/channel) the model omitted."""
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}

    # A Zalo identity is linked once. Delivery contact numbers are stored on the
    # cart via set_delivery and must never silently switch the member identity.
    if name == "link_channel" and ctx.get("userId"):
        return {
            "already_linked": True,
            "userId": ctx["userId"],
            "message": "Tài khoản Zalo này đã liên kết thành viên. Không đổi sang SĐT khác. "
                       "Nếu khách cung cấp SĐT nhận hàng khác, chỉ dùng set_delivery.",
        }

    # ── Deterministic login gate ──────────────────────────────────────────────
    # Tie the "please link your phone" ask to INTENT rather than nagging every
    # turn. The model only reaches for these tools when the user's message is
    # about member data or confirming an order, so intercepting them here re-asks
    # at exactly the right moments — no keyword guessing.
    if not ctx.get("userId"):
        if name in MEMBER_REQUIRED:
            ctx["linkAsked"] = True
            ctx["pendingAfterLink"] = {"name": name, "args": dict(args)}
            return {"needs_link": True,
                    "customer_message":
                        "Được nha. Trước khi mình mở thông tin thành viên, Zalo này cần "
                        "liên kết với một SĐT thành viên KFC.\n\n"
                        "Liên kết một lần là được:\n"
                        "- Lần sau bạn có thể xem điểm, lịch sử đơn và đặt lại món mà không "
                        "cần nhập SĐT lại.\n"
                        "- Mỗi tài khoản Zalo chỉ xem thông tin của SĐT thành viên đã liên kết.\n"
                        "- Khi đặt món, bạn vẫn có thể dùng SĐT nhận hàng khác mà không ảnh "
                        "hưởng tài khoản thành viên.\n\n"
                        "Bạn đồng ý thì gửi mình SĐT thành viên muốn liên kết nhé.",
                    "message": "Hãy mời khách gửi SỐ ĐIỆN THOẠI muốn liên kết với tài khoản "
                               "Zalo này. Nói rõ: sau khi xác nhận, số này sẽ được ghi nhớ để "
                               "các lần sau xem điểm/lịch sử mà không phải nhập lại. Khi khách "
                               "đồng ý và gửi số, gọi link_channel(phone=...)."}
        if name == "place_order" and not ctx.get("orderLinkPitched"):
            # Ordering stays anonymous-friendly: pitch linking ONCE per order, but
            # let the customer decline and still check out (they'll re-call place_order).
            ctx["orderLinkPitched"] = True
            ctx["linkAsked"] = True
            pending_args = dict(args)
            if not pending_args.get("cartId") and ctx.get("cartId"):
                pending_args["cartId"] = ctx["cartId"]
            ctx["pendingAfterLink"] = {"name": name, "args": pending_args}
            return {"needs_link": "optional",
                    "customer_message":
                        "Trước khi chốt, mình hỏi nhanh một chút: bạn có muốn liên kết SĐT "
                        "thành viên với Zalo này để tích điểm không? Chỉ cần liên kết một lần, "
                        "lần sau mình sẽ tự nhận ra bạn; SĐT nhận hàng vẫn có thể là số khác.\n\n"
                        "Muốn liên kết thì gửi mình SĐT thành viên nhé. Không cần cũng không "
                        "sao, mình vẫn chốt đơn bình thường.",
                    "message": "Trước khi chốt đơn: hỏi khách có muốn liên kết SỐ ĐIỆN THOẠI "
                               "thành viên với tài khoản Zalo này để tích điểm không. Nói rõ số "
                               "được ghi nhớ cho những lần sau. Chỉ gọi link_channel khi khách "
                               "đồng ý; nếu không, gọi lại place_order để chốt đơn ẩn danh. "
                               "SĐT người nhận hàng không tự động trở thành SĐT thành viên."}

    if name in NEEDS_CART and not args.get("cartId") and ctx.get("cartId"):
        args["cartId"] = ctx["cartId"]
    if name == "create_cart":
        # Identity/channel fields come from the trusted request context, never
        # from model-supplied arguments (the model has emitted invalid "chat").
        args["channel"] = ctx.get("channel", "zalo")
        if ctx.get("userId"):
            args["userId"] = ctx["userId"]
        else:
            args.pop("userId", None)
    if name in ("check_loyalty", "my_orders", "reorder_last") and ctx.get("userId"):
        args["userId"] = ctx["userId"]
    if name == "reorder_last":
        args["channel"] = ctx.get("channel", "zalo")
    if name == "get_recommendations":
        c = args.get("context") or {}
        c.setdefault("cartId", ctx.get("cartId"))
        c["userId"] = ctx.get("userId")
        c["channel"] = ctx.get("channel", "zalo")
        args["context"] = c
    if name == "link_channel":
        args["channel"] = ctx.get("channel", "zalo")
        args["externalId"] = ctx.get("externalId") or ctx.get("sessionId")
    if name == "handoff":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        args.setdefault("externalId", ctx.get("externalId"))
        args.setdefault("sessionId", ctx.get("sessionId"))
    if name == "place_order":
        # QR payment needs the OA-scoped id so the pay webhook can push back.
        args["externalId"] = ctx.get("externalId")
    try:
        result = fn(**args)
        if name == "handoff" and isinstance(result, dict) and result.get("ok"):
            result["customer_message"] = (
                "Trường hợp này cần nhân viên hỗ trợ trực tiếp. Mình đã chuyển yêu cầu "
                "của bạn vào hàng chờ hỗ trợ rồi. Bạn vui lòng chờ một chút nhé — "
                "nhân viên sẽ tiếp tục phản hồi trong cuộc trò chuyện này."
            )
        return result
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
            ctx["identityUser"] = result.get("user") or {}
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
        ctx["pendingAfterLink"] = None
    # QR checkout produced a scannable image → transport sends it after the reply.
    if result.get("qrImageUrl"):
        ctx["pendingImageUrl"] = result["qrImageUrl"]


def _finish(session_id, messages, ctx, reply, trace):
    messages = _bounded_messages(messages)
    save_session(
        session_id, messages,
        state={"userId": ctx.get("userId"),
               "linkAsked": bool(ctx.get("linkAsked")),
               "orderLinkPitched": bool(ctx.get("orderLinkPitched")),
               "pendingAfterLink": ctx.get("pendingAfterLink")},
        cart_id=ctx.get("cartId"),
        conversation_started_at=ctx.get("conversationStartedAt"),
    )
    return {"reply": reply, "toolTrace": trace,
            "cartId": ctx.get("cartId") or None, "userId": ctx.get("userId"),
            "imageUrl": ctx.get("pendingImageUrl")}


def _resume_pending_link(user_message, ctx):
    """Link + resume the gated action when the requested phone arrives.

    This is deliberately orchestration-level: checkout/member correctness must
    not depend on whether the LLM remembers to emit `link_channel` next turn.
    """
    pending = ctx.get("pendingAfterLink")
    phone = _extract_phone(user_message) if pending and not ctx.get("userId") else None
    if not phone:
        return [], []

    trace = []
    linked = _run_tool("link_channel", {"phone": phone}, ctx)
    _track("link_channel", linked, ctx)
    trace.append({"tool": "link_channel", "args": {"phone": phone}, "automatic": True})
    if not linked.get("linked"):
        return [f"[HỆ THỐNG] Liên kết SĐT {phone} thất bại: {json.dumps(linked, ensure_ascii=False)}"], trace

    notes = [f"[HỆ THỐNG] Đã tự động liên kết SĐT {phone} theo yêu cầu ở lượt trước."]
    name = pending.get("name")
    if name in DISPATCH:
        args = dict(pending.get("args") or {})
        result = _run_tool(name, args, ctx)
        _track(name, result, ctx)
        trace.append({"tool": name, "args": args, "automatic": True})
        notes.append(
            f"[HỆ THỐNG] Đã tiếp tục thao tác {name}; kết quả dữ liệu: "
            f"{json.dumps(result, ensure_ascii=False, default=str)}"
        )
        if not result.get("needs_link"):
            ctx["pendingAfterLink"] = None
    return notes, trace


def chat(session_id, user_message, ctx=None):
    """
    Run one user turn through the agent. Returns {reply, toolTrace, cartId, userId}.
    `ctx` carries channel/externalId/userId for tool injection; cartId/userId
    are restored from the persisted session when not supplied.
    """
    ctx = ctx or {}
    ctx["sessionId"] = session_id

    session = load_session(session_id)
    now = datetime.now(timezone.utc)
    expired = _conversation_expired(session, now)
    state = {} if expired else (session.get("state") or {})
    ctx["conversationStartedAt"] = (
        now if expired else (_as_utc(session.get("conversationStartedAt")) or now)
    )
    if expired:
        # Persist an explicit clear; save_session treats None as "leave unchanged".
        ctx["cartId"] = ""
    if not ctx.get("cartId") and not expired:
        ctx["cartId"] = session.get("cartId") or None
    if not ctx.get("userId") and not ctx.get("externalId"):
        ctx["userId"] = state.get("userId")
    ctx["linkAsked"] = ctx.get("linkAsked") or state.get("linkAsked", False)
    ctx["orderLinkPitched"] = ctx.get("orderLinkPitched") or state.get("orderLinkPitched", False)
    ctx["pendingAfterLink"] = ctx.get("pendingAfterLink") or state.get("pendingAfterLink")

    # Durable identity is authoritative on EVERY channel turn. Never let a stale
    # session.state.userId mask a missing/unlinked backend identity.
    identity = None
    if ctx.get("externalId"):
        identity = resolve_identity(ctx.get("channel", "zalo"), ctx["externalId"])
        if identity.get("linked"):
            ctx["userId"] = str(identity["user"]["id"])
            ctx["identityUser"] = identity.get("user") or {}
        else:
            ctx["userId"] = None
            ctx["identityUser"] = {}

    messages = [] if expired else (session.get("messages") or [])
    if not messages:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

    blocked_reply = _other_member_phone_reply(user_message, ctx)
    if blocked_reply:
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": blocked_reply})
        return _finish(session_id, messages, ctx, blocked_reply, [])

    # No proactive login pitch — the agent only asks for a phone number when the
    # customer's intent needs it (member tools → needs_link; place_order → optional
    # pitch), handled by the gate in _run_tool. Keeps the greeting natural.
    turn_notes, trace = _resume_pending_link(user_message, ctx)
    messages.append({"role": "user", "content": user_message})

    if not llm_client.available():
        reply = "Xin lỗi, trợ lý đặt món đang tạm bảo trì. Bạn thử lại sau ít phút nhé!"
        messages.append({"role": "assistant", "content": reply})
        return _finish(session_id, messages, ctx, reply, trace)

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            msg = llm_client.chat(
                _messages_for_llm(messages, ctx, turn_notes),
                tools=TOOL_DEFINITIONS,
                temperature=0.3,
            )
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
            # Identity onboarding and the optional checkout pitch use fixed,
            # complete customer copy instead of relying on an LLM paraphrase.
            if result.get("customer_message"):
                reply = result["customer_message"]
                messages.append({"role": "assistant", "content": reply})
                return _finish(session_id, messages, ctx, reply, trace)

    # Ran out of rounds — return a safe fallback.
    return _finish(session_id, messages, ctx,
                   "Xin lỗi, mình cần thêm thông tin để tiếp tục.", trace)
