"""One chat completions call to an OpenAI-compatible endpoint, shared by narration and questions.

Tries structured output first, then asks plainly if the server rejects the extras, and retries one
transient failure. Returns the answer's text or None, and never raises: whoever calls it degrades.
"""

import logging
from typing import Any

import httpx

from ..config import Settings
from .http import USER_AGENT

log = logging.getLogger(__name__)


async def complete(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    schema_name: str,
    schema: dict[str, Any],
    max_tokens: int,
    temperature: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    payload: dict[str, Any] = {
        "model": settings.narration_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    extras: dict[str, Any] = {
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
        # vLLM's switch for templates with a reasoning mode. Servers that do not know it may reject
        # the request, which is what the plain retry below is for.
        "chat_template_kwargs": {"enable_thinking": settings.narration_thinking},
    }
    headers = {"User-Agent": USER_AGENT}
    if settings.narration_api_key:
        headers["Authorization"] = f"Bearer {settings.narration_api_key}"
    url = f"{(settings.narration_base_url or '').rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=settings.narration_timeout_s, transport=transport, headers=headers) as client:
        body = payload | extras
        retried = False
        # At most: structured, then plain, then plain once more after a transient failure.
        for _ in range(3):
            try:
                response = await client.post(url, json=body)
            except httpx.TransportError as exc:
                log.warning("%s request failed: %s", schema_name, exc)
                if retried:
                    return None
                retried = True
                continue
            if response.status_code in (400, 422) and body is not payload:
                # The server rejects an extra it does not support: ask plainly instead.
                log.info("%s endpoint rejected structured output (HTTP %s)", schema_name, response.status_code)
                body = payload
                continue
            if response.status_code >= 500 and not retried:
                retried = True
                continue
            if response.status_code >= 400:
                log.warning("%s endpoint answered HTTP %s: %.200s", schema_name, response.status_code, response.text)
                return None
            try:
                return response.json()["choices"][0]["message"]["content"] or None
            except (ValueError, KeyError, IndexError, TypeError):
                log.warning("%s endpoint answered an unexpected body: %.200s", schema_name, response.text)
                return None
    return None
