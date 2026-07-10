"""
L5 — LLM re-ranker + Vietnamese copywriter (OpenAI).

Two jobs, BOTH strictly over the candidate set:
  1. pick & order the best `limit` items given full context
  2. write a short persuasive VN line per pick

Guardrail (ported from Claw-a-thon rag/recommend.py): every returned sku is
validated against the candidate set; invented items are DROPPED. If no API key
or the call fails, we fall back to the top-N candidates with template copy.
"""
import json
from app.config import config

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


SYSTEM = (
    "Bạn là trợ lý gợi ý món tại kiosk KFC Việt Nam. "
    "CHỈ được chọn trong danh sách ứng viên được cung cấp — KHÔNG tự nghĩ ra món mới. "
    "Chọn tối đa N món phù hợp nhất với ngữ cảnh (giờ trong ngày, giỏ hàng hiện tại) "
    "và viết 1 câu mời ngắn, thân thiện bằng tiếng Việt cho mỗi món. "
    'Trả về JSON: {"picks":[{"sku":"...","copy":"..."}]}'
)


def _template_copy(name):
    return f"Thêm {name} cho bữa ăn trọn vị nhé!"


def llm_rerank(candidates, ctx, name_of, limit=3):
    """Returns (picks, used_llm). picks: [{sku, copy, ...}] limited to `limit`."""
    if not candidates:
        return [], False

    client = _get_client()
    if client is None:
        picks = candidates[:limit]
        for c in picks:
            c["copy"] = _template_copy(name_of(c["sku"]))
        return picks, False

    cand_view = [{"sku": c["sku"], "name": name_of(c["sku"]), "reason": c.get("reason", "")}
                 for c in candidates[:12]]
    user = (
        f"Ngữ cảnh: giờ={ctx.get('timeOfDay')}, hình thức={ctx.get('dineMode')}, "
        f"kênh={ctx.get('channel')}. N={limit}.\n"
        f"Ứng viên (chỉ chọn trong đây):\n{json.dumps(cand_view, ensure_ascii=False)}"
    )
    try:
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
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
            picks = candidates[:limit]
            for c in picks:
                c["copy"] = _template_copy(name_of(c["sku"]))
            return picks, False
        return picks[:limit], True
    except Exception:
        picks = candidates[:limit]
        for c in picks:
            c["copy"] = _template_copy(name_of(c["sku"]))
        return picks, False
