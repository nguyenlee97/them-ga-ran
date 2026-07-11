"""
Raw OpenAI-compatible chat client — plain httpx POST, no SDK.

Mirrors the PROVEN flow from random-bullshlt backend/services/reportGenerator.js:
a direct fetch to /chat/completions with a Bearer key (that call works reliably
on this machine/network, while the openai Python SDK raises APIConnectionError).
Also works unchanged against any OpenAI-compatible base URL (GreenNode MaaS).
"""
import httpx
from app.config import config

_BASE = (config.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
_client = httpx.Client(timeout=30.0)


class LLMError(Exception):
    pass


def available():
    return bool(config.OPENAI_API_KEY)


def chat(messages, tools=None, temperature=0.3, response_format=None, tool_choice=None):
    """POST /chat/completions → the assistant `message` dict (plain dict with
    "content" and optionally "tool_calls"). Raises LLMError on any failure."""
    if not available():
        raise LLMError("no_api_key")
    body = {"model": config.OPENAI_MODEL, "messages": messages, "temperature": temperature}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"
    if response_format:
        body["response_format"] = response_format
    try:
        r = _client.post(
            f"{_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json=body,
        )
    except Exception as e:
        raise LLMError(f"{type(e).__name__}: {str(e)[:200]}")
    if r.status_code >= 400:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]
    except (KeyError, IndexError):
        raise LLMError(f"unexpected response shape: {str(data)[:200]}")
