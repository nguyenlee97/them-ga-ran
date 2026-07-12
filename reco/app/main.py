"""
KFC recommendation service — FastAPI.

Single endpoint POST /recommend serves BOTH the kiosk and the chat agent (via
the backend's /api/recommend proxy). Ensemble is graceful-degrading, so this
stays up even if OpenAI/Qdrant are unavailable.
"""
import json
from pathlib import Path
from typing import Any, Optional
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from app.config import config
from app.pipeline.ensemble import recommend as run_recommend

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"

app = FastAPI(title="KFC Reco Service", version="0.1.0")


class Context(BaseModel):
    storeId: Optional[str] = None
    dineMode: Optional[str] = "dine_in"
    timeOfDay: Optional[str] = None
    dayOfWeek: Optional[str] = None
    channel: Optional[str] = "kiosk"
    cart: list[dict[str, Any]] = Field(default_factory=list)
    userId: Optional[str] = None
    cartId: Optional[str] = None


class RecommendRequest(BaseModel):
    slot: str = "cart"  # cart | item_added | checkout | browse | greeting
    context: Context = Field(default_factory=Context)
    limit: int = 3


@app.get("/health")
def health():
    return {"ok": True, "service": "kfc-reco", "llm": bool(config.OPENAI_API_KEY)}


@app.post("/recommend")
async def recommend(req: RecommendRequest):
    ctx = req.context.model_dump()
    # ensemble is sync (pymongo + optional CPU embed) → run off the event loop
    result = await run_in_threadpool(run_recommend, req.slot, ctx, req.limit)
    return result


# ── P4 chat agent — test endpoint (Zalo webhook wiring comes later) ──────────
class ChatRequest(BaseModel):
    sessionId: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)  # channel, externalId, userId, cartId


@app.post("/agent/chat")
async def agent_chat(req: ChatRequest):
    from app.agent.loop import chat
    result = await run_in_threadpool(chat, req.sessionId, req.message, dict(req.context))
    return result


@app.get("/agent/ui")
def agent_ui():
    """Web chat harness — dev/demo surface for the SAME agent that will sit
    behind the Zalo OA webhook. Open http://localhost:8080/agent/ui"""
    from app.agent.chat_ui import CHAT_HTML
    return HTMLResponse(CHAT_HTML)


# ── P4 Zalo OA webhook adapter ───────────────────────────────────────────────
# Same channel-agnostic chat() sits behind this; only the transport differs.
GREETING = (
    "Xin chào! Mình là trợ lý đặt món KFC giao tận nơi 🍗. "
    "Bạn có thể gửi SỐ ĐIỆN THOẠI để đăng nhập (tích điểm, ưu đãi thành viên), "
    "hoặc nhắn \"xem menu\" / tên món để bắt đầu nhé!"
)


def _handle_zalo_message(user_id: str, text: str):
    """Run one user turn through the agent and send the reply back to Zalo.
    Runs in a threadpool via BackgroundTasks so the webhook can 200 instantly."""
    from app.agent.loop import chat
    from app.agent.zalo import send_text, send_image
    image_url = None
    try:
        result = chat(user_id, text, {"channel": "zalo", "externalId": user_id})
        reply = (result or {}).get("reply") or "…"
        image_url = (result or {}).get("imageUrl")
        print(f"[zalo] {user_id}: {text!r} -> {reply!r}" + (f" [+image]" if image_url else ""))
    except Exception as e:  # never let the demo hang on an error
        print(f"[zalo] chat failed for {user_id}: {e}")
        reply = "Xin lỗi, hệ thống đang bận một chút. Bạn thử lại giúp mình nhé!"
    try:
        send_text(user_id, reply)
    except Exception as e:
        print(f"[zalo] send failed for {user_id}: {e}")
    # QR checkout: deliver the scannable image right after the text reply.
    if image_url:
        try:
            send_image(user_id, image_url)
        except Exception as e:
            print(f"[zalo] send_image failed for {user_id}: {e}")


def _handle_zalo_audio(user_id: str, audio_url: str):
    """Download + transcribe a completed voice note, then reuse the text flow."""
    from app.agent.transcription import transcribe_audio
    from app.agent.zalo import download_audio, send_text
    try:
        audio = download_audio(audio_url)
        transcript = transcribe_audio(audio)
        print(f"[zalo] audio transcribed for {user_id}: {transcript!r}")
    except Exception as e:
        print(f"[zalo] audio failed for {user_id}: {type(e).__name__}: {str(e)[:300]}")
        try:
            send_text(
                user_id,
                "Mình chưa nghe rõ tin nhắn này. Bạn thử gửi lại đoạn ngắn hơn "
                "hoặc nhắn chữ giúp mình nhé.",
            )
        except Exception as send_error:
            print(f"[zalo] audio fallback send failed for {user_id}: {send_error}")
        return
    _handle_zalo_message(user_id, transcript)


@app.get("/zalo/webhook")
def zalo_webhook_health():
    """Zalo pings the URL; must return 200."""
    return {"ok": True, "service": "kfc-zalo-webhook"}


@app.get("/zalo/oauth/login")
def zalo_oauth_login():
    """OA admin opens this to (re)grant consent → redirects to Zalo's permission page."""
    from app.agent.zalo import start_consent
    return RedirectResponse(start_consent())


@app.get("/zalo/oauth/callback")
def zalo_oauth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """Zalo redirects here after consent; we swap the code for a token pair."""
    from app.agent.zalo import finish_consent
    if error:
        return HTMLResponse(f"<h3>Zalo consent error: {error}</h3><p>{error_description}</p>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h3>Missing code/state — start at /zalo/oauth/login</h3>", status_code=400)
    try:
        finish_consent(code, state)
    except Exception as e:
        return HTMLResponse(f"<h3>Token exchange failed</h3><pre>{e}</pre>", status_code=400)
    return HTMLResponse("<h3>✅ Zalo OA linked — fresh tokens stored. You can close this tab.</h3>")


@app.post("/zalo/webhook")
async def zalo_webhook(request: Request, background: BackgroundTasks):
    from app.agent.zalo import verify_signature, parse_event, extract_audio_url
    raw = await request.body()
    mac = request.headers.get("X-ZEvent-Signature", "")
    try:
        body = json.loads(raw or b"{}")
    except Exception:
        body = {}
    if not verify_signature(raw, body.get("timestamp", ""), mac):
        print(f"[zalo] bad_signature — mac_header={mac!r} raw={body}")
        return JSONResponse({"error": "bad_signature"}, status_code=403)

    event, user_id, text = parse_event(body)
    print(f"[zalo] webhook event={event!r} user={user_id!r} text={text!r} raw={body}")
    if event == "user_send_text" and user_id and text:
        background.add_task(_handle_zalo_message, user_id, text)
    elif event == "user_send_audio" and user_id:
        audio_url = extract_audio_url(body)
        if audio_url:
            background.add_task(_handle_zalo_audio, user_id, audio_url)
        else:
            from app.agent.zalo import send_text
            background.add_task(
                send_text, user_id,
                "Mình chưa mở được tin nhắn thoại này. Bạn gửi lại hoặc nhắn chữ giúp mình nhé.",
            )
    elif event == "follow" and user_id:
        from app.agent.zalo import send_text
        background.add_task(send_text, user_id, GREETING)
    # 200 immediately; any reply is delivered asynchronously via the Send API.
    return {"ok": True}


@app.get("/zalo/pay/qr")
def zalo_pay_qr(token: str = ""):
    """Serve the scannable QR PNG that encodes this token's pay URL."""
    base = config.PUBLIC_BASE_URL.rstrip("/")
    pay_url = f"{base}/zalo/pay?token={token}"
    try:
        import io
        import qrcode
        img = qrcode.make(pay_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as e:
        print(f"[zalo] qr generation failed: {e}")
        return JSONResponse({"error": "qr_failed"}, status_code=500)


@app.get("/zalo/pay")
def zalo_pay(token: str = ""):
    """Simulated payment success: mark the order paid, push a confirmation to the
    customer, and show a success page. This is what the QR resolves to when scanned."""
    from app.db import get_db
    import httpx
    db = get_db()
    pay = db.zalo_payments.find_one({"_id": token})
    if not pay:
        return HTMLResponse("<h3>Liên kết thanh toán không hợp lệ hoặc đã hết hạn.</h3>", status_code=404)
    if pay.get("status") == "paid":
        return HTMLResponse("<h3>✅ Đơn hàng này đã được thanh toán. Cảm ơn bạn!</h3>")
    try:
        httpx.post(f"{config.BACKEND_URL}/api/orders/{pay['orderId']}/pay", timeout=10)
    except Exception as e:
        print(f"[zalo] pay: backend mark-paid failed: {e}")
    db.zalo_payments.update_one({"_id": token}, {"$set": {"status": "paid"}})
    ext = pay.get("externalId")
    if ext:
        try:
            from app.agent.zalo import send_text
            amt = int(pay.get("amount") or 0)
            send_text(ext, f"✅ Thanh toán thành công {amt:,}đ! Đơn KFC của bạn đang được "
                           f"chuẩn bị và sẽ sớm giao tới 🍗. Cảm ơn bạn đã đặt hàng!")
        except Exception as e:
            print(f"[zalo] pay: confirmation push failed: {e}")
    return HTMLResponse("<h3>✅ Thanh toán thành công! Mời bạn quay lại Zalo để xem xác nhận đơn hàng.</h3>")


@app.get("/")
def root():
    """Domain-verification landing page (meta-tag method) + liveness."""
    meta = config.ZALO_VERIFY_META
    tag = (f'<meta name="zalo-platform-site-verification" content="{meta}" />'
           if meta else "")
    return HTMLResponse(
        f'<!doctype html><html><head><meta charset="utf-8">{tag}'
        f'<title>KFC × Pawgrammers</title></head>'
        f'<body>KFC ordering agent — OK</body></html>'
    )


@app.get("/{fname}")
def serve_public(fname: str):
    """Serve the Zalo domain-verification HTML file if it was dropped into
    reco/public/ (file method). Declared last so it never shadows real routes."""
    f = PUBLIC_DIR / fname
    if fname.endswith(".html") and f.is_file():
        return HTMLResponse(f.read_text(encoding="utf-8"))
    return JSONResponse({"error": "not_found"}, status_code=404)
