#!/usr/bin/env python3
"""
Shared API client for the autonovel pipeline.

Supports two providers:
  - "anthropic" (default) — Anthropic Messages API
  - "openrouter" — OpenAI-compatible Chat Completions API

Configuration via .env:
  AUTONOVEL_API_PROVIDER      — "anthropic" or "openrouter"
  AUTONOVEL_WRITER_MODEL      — model for creative generation
  AUTONOVEL_JUDGE_MODEL       — model for evaluation/scoring
  AUTONOVEL_REVIEW_MODEL      — model for deep literary review
  ANTHROPIC_API_KEY           — key for Anthropic provider
  OPENROUTER_API_KEY          — key for OpenRouter provider
  AUTONOVEL_API_BASE_URL      — base URL for Anthropic (default: https://api.anthropic.com)
  OPENROUTER_BASE_URL         — base URL for OpenRouter (default: https://openrouter.ai)
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# --- Provider config ---
API_PROVIDER = os.environ.get("AUTONOVEL_API_PROVIDER", "anthropic").lower()

# --- Model config (3 roles) ---
MODELS = {
    "writer": os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6"),
    "judge": os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6"),
    "review": os.environ.get("AUTONOVEL_REVIEW_MODEL", "claude-opus-4-6"),
}

# --- Anthropic config ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")

# --- OpenRouter config ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai")


def call_llm(
    role: str,
    prompt: str,
    *,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: int = 600,
) -> str:
    """Call an LLM and return the response text.

    Args:
        role: "writer", "judge", or "review" — selects model from env config.
        prompt: The user message content.
        system: Optional system prompt.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.
        timeout: Request timeout in seconds.
    """
    model = MODELS.get(role)
    if model is None:
        raise ValueError(f"Unknown role {role!r}. Expected: writer, judge, review")

    if API_PROVIDER == "openrouter":
        return _call_openrouter(model, prompt, system, temperature, max_tokens, timeout)
    elif API_PROVIDER == "anthropic":
        return _call_anthropic(model, prompt, system, temperature, max_tokens, timeout)
    else:
        raise ValueError(
            f"Unknown API provider {API_PROVIDER!r}. Expected: anthropic, openrouter"
        )


def _call_anthropic(model, prompt, system, temperature, max_tokens, timeout):
    import httpx

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "context-1m-2025-08-07",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    resp = httpx.post(
        f"{ANTHROPIC_BASE_URL}/v1/messages",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _call_openrouter(model, prompt, system, temperature, max_tokens, timeout):
    import httpx

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "content-type": "application/json",
        "HTTP-Referer": "https://github.com/autonovel",
        "X-Title": "autonovel",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    resp = httpx.post(
        f"{OPENROUTER_BASE_URL}/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
