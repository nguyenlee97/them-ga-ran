"""
L5 — LLM re-ranker + Vietnamese copywriter.

Two jobs, BOTH strictly over the candidate set:
  1. pick & order the best `limit` items given full context
  2. write a short persuasive VN line per pick

Guardrail (ported from Claw-a-thon rag/recommend.py): every returned sku is
validated against the candidate set; invented items are DROPPED. If no API key
or the call fails, we fall back to the top-N candidates with template copy.

Uses app.llm_client (raw httpx POST, no SDK) — the flow proven to work on
this machine by random-bullshlt's reportGenerator.js.
"""
import re
from app import llm_client

# MaaS models (minimax etc.) leak <think> reasoning and markdown fences.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _extract_json(raw):
    import json
    raw = _THINK_RE.sub("", raw or "")
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(m.group()) if m else {}


SYSTEM = (
    "Bạn là trợ lý gợi ý món tại kiosk KFC Việt Nam. "
    "CHỈ được chọn trong danh sách ứng viên được cung cấp — KHÔNG tự nghĩ ra món mới. "
    "Chọn tối đa N món phù hợp nhất với ngữ cảnh (giờ trong ngày, giỏ hàng hiện tại) "
    "và viết 1 câu mời ngắn, thân thiện bằng tiếng Việt cho mỗi món. "
    'Trả về JSON: {"picks":[{"sku":"...","copy":"..."}]}'
)


def _template_copy(name):
    return f"Thêm {name} cho bữa ăn trọn vị nhé!"


def _fallback(candidates, name_of, limit):
    picks = candidates[:limit]
    for c in picks:
        c["copy"] = _template_copy(name_of(c["sku"]))
    return picks, False


def llm_rerank(candidates, ctx, name_of, limit=3):
    """Returns (picks, used_llm). picks: [{sku, copy, ...}] limited to `limit`."""
    import json
    if not candidates:
        return [], False
    if not llm_client.available():
        return _fallback(candidates, name_of, limit)

    cand_view = [{"sku": c["sku"], "name": name_of(c["sku"]), "reason": c.get("reason", "")}
                 for c in candidates[:12]]
    user = (
        f"Ngữ cảnh: giờ={ctx.get('timeOfDay')}, hình thức={ctx.get('dineMode')}, "
        f"kênh={ctx.get('channel')}. N={limit}.\n"
        f"Ứng viên (chỉ chọn trong đây):\n{json.dumps(cand_view, ensure_ascii=False)}"
    )
    try:
        # json_object mode is OpenAI-specific; MaaS output is parsed defensively.
        rf = {"type": "json_object"} if llm_client.supports_json_object_mode() else None
        msg = llm_client.chat(
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            temperature=0.4, response_format=rf,
        )
        data = _extract_json(msg.get("content"))
        valid = {c["sku"]: c for c in candidates}
        picks, dropped = [], 0
        for p in data.get("picks", []):
            sku = p.get("sku")
            if sku in valid:  # guardrail: candidate-set validation
                item = dict(valid[sku])
                item["copy"] = p.get("copy") or _template_copy(name_of(sku))
                item["strategy"] = item.get("strategy", "") + "+llm_rerank"
                picks.append(item)
            else:
                dropped += 1
        if not picks:  # LLM returned only junk → fall back
            return _fallback(candidates, name_of, limit)
        return picks[:limit], True
    except Exception as e:
        print(f"[llm_rerank] LLM call failed — template fallback. ({type(e).__name__}: {str(e)[:200]})")
        return _fallback(candidates, name_of, limit)
