"""
Tool-calling orchestration loop for the KFC chat ordering agent.

Thin orchestrator: the LLM decides WHICH tool to call; tools.py calls the
backend, which owns all state and validation. Bounded iterations to avoid loops.
Channel-agnostic by design — the web harness, Zalo OA webhook, and Messenger
all feed the same chat() entrypoint; only the transport differs.

Session persistence: cartId and userId survive across turns (Mongo-backed),
are injected into tool args when the model omits them, and the cart reference
is cleared after a successful place_order so the next order starts fresh.
"""
import json
from app.config import config
from app.agent.registry import TOOL_DEFINITIONS, SYSTEM_PROMPT
from app.agent.tools import DISPATCH, attach_user_to_cart
from app.agent.session import load_session, save_session

MAX_TOOL_ROUNDS = 6
NEEDS_CART = {"add_to_cart", "view_cart", "remove_from_cart", "apply_voucher", "place_order"}

_client = None


def _get_client():
    global _client
    if _client is None and config.OPENAI_API_KEY:
        try:
            from openai import OpenAI
            kwargs = {"api_key": config.OPENAI_API_KEY}
            if config.OPENAI_BASE_URL:
                kwargs["base_url"] = config.OPENAI_BASE_URL
            _client = OpenAI(**kwargs)
        except Exception as e:
            print(f"[agent] OpenAI client init failed: {e}")
            _client = False  # sentinel: don't retry on every request
    return _client or None


def _run_tool(name, args, ctx):
    """Execute a tool, injecting session context (cartId/userId/channel) the model omitted."""
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}
    if name in NEEDS_CART and not args.get("cartId") and ctx.get("cartId"):
        args["cartId"] = ctx["cartId"]
    if name == "create_cart":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        if ctx.get("userId"):
            args.setdefault("userId", ctx["userId"])
    if name == "check_loyalty" and not args.get("userId") and ctx.get("userId"):
        args["userId"] = ctx["userId"]
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
    try:
        return fn(**args)
    except Exception as e:
        return {"error": "tool_failed", "detail": str(e)[:200]}


def _track(name, result, ctx):
    """Update session context from tool results."""
    if not isinstance(result, dict):
        return
    if name == "create_cart" and result.get("cartId"):
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


def _finish(session_id, messages, ctx, reply, trace):
    save_session(
        session_id, messages,
        state={"userId": ctx.get("userId")},
        cart_id=ctx.get("cartId"),
    )
    return {"reply": reply, "toolTrace": trace,
            "cartId": ctx.get("cartId") or None, "userId": ctx.get("userId")}


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

    messages = session.get("messages") or []
    if not messages:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    if client is None:
        reply = "(Agent chưa cấu hình OPENAI_API_KEY — đây là bản khung. Backend + tools đã sẵn sàng.)"
        messages.append({"role": "assistant", "content": reply})
        return _finish(session_id, messages, ctx, reply, [])

    trace = []
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL, messages=messages,
            tools=TOOL_DEFINITIONS, tool_choice="auto", temperature=0.3,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return _finish(session_id, messages, ctx, msg.content or "", trace)

        # Execute each requested tool and feed results back.
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            result = _run_tool(name, args, ctx)
            _track(name, result, ctx)
            trace.append({"tool": name, "args": args})
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Ran out of rounds — return a safe fallback.
    return _finish(session_id, messages, ctx,
                   "Xin lỗi, mình cần thêm thông tin để tiếp tục.", trace)
