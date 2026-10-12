"""Unauthenticated meta endpoints: health check and provider catalog."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings

router = APIRouter(tags=["meta"])


@router.api_route("/health", methods=["GET", "HEAD"])
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "version": settings.version}


@router.get("/providers")
async def providers() -> dict:
    """Static catalog so the UI can populate model dropdowns without a key."""
    settings = get_settings()
    return {
        "providers": [
            {
                "id": "openai",
                "label": "OpenAI",
                "default_model": settings.openai_default_model,
                "models": [settings.openai_default_model, "gpt-5.1-mini", "gpt-5"],
                "key_hint": "sk-...",
            },
            {
                "id": "anthropic",
                "label": "Anthropic (Claude)",
                "default_model": settings.anthropic_default_model,
                "models": [settings.anthropic_default_model, "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-5-5", "claude-haiku-4-5", "claude-fable-5-1"],
                "key_hint": "sk-ant-...",
            },
            {
                "id": "kimi",
                "label": "Kimi K2 (Moonshot)",
                "default_model": settings.kimi_default_model,
                "models": [settings.kimi_default_model, "kimi-k2-turbo-preview", "kimi-k2-thinking"],
                "key_hint": "sk-...",
            },
        ]
    }
