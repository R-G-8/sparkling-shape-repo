"""
Minimal OpenRouter client (https://openrouter.ai/docs), called from the server only.

The API key comes from the OPENROUTER_API_KEY environment variable and never
reaches the browser. Tests mock `chat_completion`; they never call the real API.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(Exception):
    """The LLM call failed. Safe to log; never contains the API key."""


class LLMNotConfigured(LLMError):
    pass


def chat_completion(messages, *, response_format=None, temperature=0.7, max_tokens=1500):
    """Send a chat completion request and return (content, model)."""
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise LLMNotConfigured("OPENROUTER_API_KEY is not set")

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "numbawatchd",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace")
        raise LLMError(f"OpenRouter returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMError(f"Couldn't reach OpenRouter: {exc}") from exc
    except ValueError as exc:
        raise LLMError("OpenRouter sent a response that isn't JSON") from exc

    if "error" in body:
        raise LLMError(f"OpenRouter error: {str(body['error'])[:500]}")
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("OpenRouter response had no message content") from exc
    if not content:
        raise LLMError("OpenRouter returned an empty message")

    usage = body.get("usage") or {}
    logger.info(
        "openrouter call model=%s prompt_tokens=%s completion_tokens=%s",
        body.get("model"),
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
    )
    return content, body.get("model") or settings.OPENROUTER_MODEL
