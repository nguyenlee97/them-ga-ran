"""
KFC recommendation service — FastAPI.

Single endpoint POST /recommend serves BOTH the kiosk and the chat agent (via
the backend's /api/recommend proxy). Ensemble is graceful-degrading, so this
stays up even if OpenAI/Qdrant are unavailable.
"""
from typing import Any, Optional
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import config
from app.pipeline.ensemble import recommend as run_recommend

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
