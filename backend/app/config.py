"""Application settings. Values come from env vars (prefix APP_) or defaults.

No provider API keys live here -- keys arrive per request (dashboard) or from the
local environment at call time (terminal). This keeps secrets out of the cached
settings object.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Deep Research Studio API"
    assistant_name: str = "Andon Assistant"
    version: str = "0.2.0"
    log_level: str = "INFO"

    # Comma-separated list of allowed CORS origins ("*" allows all).
    cors_origins: str = "*"

    # Seconds allowed for a single provider call.
    request_timeout: float = 120.0

    # --- research pipeline (now also the deep_research tool) ---
    default_max_subquestions: int = 4
    search_max_results: int = 5

    # Default model per provider (client may override per request).
    openai_default_model: str = "gpt-5.1"
    anthropic_default_model: str = "claude-opus-5-5"
    kimi_default_model: str = "kimi-k2-0905-preview"
    kimi_base_url: str = "https://api.moonshot.ai/v1"

    # --- assistant / agent ---
    default_provider: str = "openai"
    # "pydantic_ai" (native function-calling, default) or "manual" (prompt-JSON).
    # Resolves to manual automatically if pydantic_ai is unavailable at runtime.
    agent_backend: str = "pydantic_ai"
    agent_max_steps: int = 6

    # --- calendar sync (optional; the background loop runs only when a provider is enabled) ---
    calendar_sync_minutes: int = 15

    # --- local-first storage ---
    # Empty -> ~/.assistant/state.db, ~/.assistant/workspace and ~/.assistant/runs
    db_path: str = ""
    file_root: str = ""
    # Per-run stage folders for workflows (deep research): plan.md, evidence.md, report.md.
    runs_dir: str = ""
    # Readable memory: facts.md mirror + candidates/ review folder (default ~/.assistant/memory).
    memory_dir: str = ""
    # When True, facts the consolidation gate picks on its own become *candidates* a person
    # approves before they are saved or recalled. The remember tool still saves directly.
    memory_review: bool = False
    # When False (default), file tools may only touch file_root. Flip to allow the
    # whole filesystem (loud warning; path-escape check is always on relative to root).
    file_unrestricted: bool = False

    @property
    def origins_list(self) -> list[str]:
        items = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return items or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
