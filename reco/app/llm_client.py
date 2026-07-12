"""
Raw OpenAI-compatible chat client — plain httpx POST, no SDK.

Mirrors the PROVEN flow from random-bullshlt backend/services/reportGenerator.js:
a direct fetch to /chat/completions with a Bearer key (that call works reliably
on this machine/network, while the openai Python SDK raises APIConnectionError).
Also supports GreenNode MaaS through its OpenAI-compatible endpoint. GreenNode
is opt-in; the existing OpenAI configuration remains the default.
"""
import httpx
from app.config import config

_client = httpx.Client(timeout=30.0)


class LLMError(Exception):
    pass


def _provider_settings():
    """Resolve credentials without mutating either provider's configuration."""
    provider = config.LLM_PROVIDER
    if provider == "greennode":
        return {
            "provider": provider,
            "api_key": config.GREENNODE_API_KEY,
            "base_url": config.GREENNODE_BASE_URL.rstrip("/"),
            "model": config.GREENNODE_MODEL,
        }
    if provider == "openai":
        return {
            "provider": provider,
            "api_key": config.OPENAI_API_KEY,
            "base_url": (config.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/"),
            "model": config.OPENAI_MODEL,
        }
    raise LLMError(f"unsupported_llm_provider:{provider}")


def provider_name():
    return _provider_settings()["provider"]


def supports_json_object_mode():
    settings = _provider_settings()
    return settings["provider"] == "openai" and not config.OPENAI_BASE_URL


def available():
    try:
        return bool(_provider_settings()["api_key"])
    except LLMError:
        return False


def chat(messages, tools=None, temperature=0.3, response_format=None, tool_choice=None):
    """POST /chat/completions → the assistant `message` dict (plain dict with
    "content" and optionally "tool_calls"). Raises LLMError on any failure."""
    settings = _provider_settings()
    if not settings["api_key"]:
        raise LLMError("no_api_key")
    body = {"model": settings["model"], "messages": messages, "temperature": temperature}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"
    if response_format:
        body["response_format"] = response_format
    try:
        r = _client.post(
            f"{settings['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {settings['api_key']}",
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
