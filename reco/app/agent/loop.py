"""
Tool-calling orchestration loop for the KFC chat ordering agent.

Thin orchestrator: the LLM decides WHICH tool to call; tools.py calls the
backend, which owns all state and validation. Bounded iterations to avoid loops.
Zalo webhook wiring comes later — this loop is channel-agnostic.
"""
import json
from app.config import config
from app.agent.registry import TOOL_DEFINITIONS, SYSTEM_PROMPT
from app.agent.tools import DISPATCH
from app.agent.session import load_session, save_session

MAX_TOOL_ROUNDS = 6

_client = None


def _get_client():
    global _client
    if _client is None and config.OPENAI_API_KEY:
        from openai import OpenAI
        kwargs = {"api_key": config.OPENAI_API_KEY}
        if config.OPENAI_BASE_URL:
            kwargs["base_url"] = config.OPENAI_BASE_URL
        _client = OpenAI(**kwargs)
    return _client


def _run_tool(name, args, ctx):
    """Execute a tool, injecting session context (cartId/userId/channel) as needed."""
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}
    # Inject known session fields when the model omits them.
    if name == "create_cart":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        args.setdefault("userId", ctx.get("userId"))
    if name == "handoff":
        args.setdefault("channel", ctx.get("channel", "zalo"))
        args.setdefault("externalId", ctx.get("externalId"))
        args.setdefault("sessionId", ctx.get("sessionId"))
    try:
        return fn(**args)
    except Exception as e:
        return {"error": "tool_failed", "detail": str(e)[:200]}


def chat(session_id, user_message, ctx=None):
    """
    Run one user turn through the agent. Returns {reply, toolTrace, cartId}.
    `ctx` carries channel/externalId/userId for tool injection.
    """
    ctx = ctx or {}
    ctx["sessionId"] = session_id

    client = _get_client()
    session = load_session(session_id)
    messages = session.get("messages") or []
    if not messages:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": user_message})

    if client is None:
        reply = "(Agent chưa cấu hình OPENAI_API_KEY — đây là bản khung. Backend + tools đã sẵn sàng.)"
        messages.append({"role": "assistant", "content": reply})
        save_session(session_id, messages)
        return {"reply": reply, "toolTrace": [], "cartId": session.get("cartId")}

    trace = []
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL, messages=messages,
            tools=TOOL_DEFINITIONS, tool_choice="auto", temperature=0.3,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            save_session(session_id, messages, cart_id=ctx.get("cartId"))
            return {"reply": msg.content or "", "toolTrace": trace, "cartId": ctx.get("cartId")}

        # Execute each requested tool and feed results back.
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            result = _run_tool(name, args, ctx)
            # Track cartId across turns.
            if name == "create_cart" and isinstance(result, dict) and result.get("_id"):
                ctx["cartId"] = result["_id"]
            trace.append({"tool": name, "args": args})
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Ran out of rounds — return last content.
    save_session(session_id, messages, cart_id=ctx.get("cartId"))
    return {"reply": "Xin lỗi, mình cần thêm thông tin để tiếp tục.", "toolTrace": trace, "cartId": ctx.get("cartId")}
