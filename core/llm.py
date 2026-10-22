"""Thin wrapper around the Claude API. Every caller must cope with `None` (no key / API error)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from core.config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def _client():
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def complete(prompt: str, system: str | None = None, model: str | None = None, max_tokens: int = 800) -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        msg = client.messages.create(
            model=model or get_settings().claude_model_reasoning,
            max_tokens=max_tokens,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as exc:  # network, auth, rate limit
        log.warning("Claude call failed: %s", exc)
        return None


def extract(
    prompt: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    model: str | None = None,
    max_tokens: int = 2000,
) -> dict | None:
    """Structured extraction via a tool call. Returns the tool input dict.

    Newer models reject a forced `tool_choice`, so the tool is offered with `auto` and the prompt tells
    the model to call it.
    """
    client = _client()
    if client is None:
        return None
    try:
        msg = client.messages.create(
            model=model or get_settings().claude_model_extraction,
            max_tokens=max_tokens,
            tools=[{"name": tool_name, "description": tool_description, "input_schema": input_schema}],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": f"{prompt}\n\nRespond only by calling the `{tool_name}` tool."}],
        )
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use":
                return block.input if isinstance(block.input, dict) else json.loads(block.input)
    except Exception as exc:
        log.warning("Claude extraction failed: %s", exc)
    return None
