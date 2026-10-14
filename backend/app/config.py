"""Runtime configuration. Everything is overridable via environment variables prefixed LEDGERLENS_.

Budget guard-rails are defaults here: Gemini Flash for every agent, LLM response cache on, Cloud Run scale-to-zero.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEDGERLENS_", env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    app_name: str = "ledgerlens"
    env: str = "dev"
    log_level: str = "INFO"

    # --- storage -----------------------------------------------------------
    storage: Literal["local", "gcp"] = "local"
    local_data_dir: Path = REPO_ROOT / "data" / "runtime"
    gcp_project: Optional[str] = Field(default=None, validation_alias=AliasChoices("LEDGERLENS_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"))
    gcs_bucket: Optional[str] = None
    firestore_database: str = "(default)"
    firestore_prefix: str = "ledgerlens"

    # --- LLM ---------------------------------------------------------------
    # auto: live when an API key is present, otherwise mock. cache_only: never call Gemini (demo safety).
    llm_mode: Literal["auto", "live", "cache_only", "mock"] = "auto"
    google_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY", "LEDGERLENS_GOOGLE_API_KEY"),
    )
    use_vertexai: bool = Field(default=False, validation_alias=AliasChoices("GOOGLE_GENAI_USE_VERTEXAI", "LEDGERLENS_USE_VERTEXAI"))
    vertex_location: str = Field(default="global", validation_alias=AliasChoices("GOOGLE_CLOUD_LOCATION", "LEDGERLENS_VERTEX_LOCATION"))
    # Budget default: Flash everywhere. Set LEDGERLENS_MODEL_PRO=gemini-3.1-pro-preview to upgrade the heavy agents.
    model_flash: str = "gemini-3.8-flash"
    model_pro: str = "gemini-3.8-flash"
    temperature: float = 0.0
    thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    media_resolution: Literal["low", "medium", "high"] = "medium"
    llm_cache_enabled: bool = True
    llm_concurrency: int = 3
    llm_timeout_seconds: int = 180
    llm_max_retries: int = 2
    # Hard stop: refuse to spend more than this in one process lifetime (USD).
    budget_cap_usd: float = 5.0

    # --- documents ---------------------------------------------------------
    max_upload_mb: int = 20
    page_render_dpi: int = 110
    llm_page_max_width: int = 1200
    synth_dir: Path = REPO_ROOT / "data" / "synth"
    demo_seed_on_startup: bool = True

    # --- api ---------------------------------------------------------------
    cors_origins: list[str] = ["*"]
    static_dir: Optional[Path] = None  # built frontend (dist) to serve at /
    admin_token: Optional[str] = None  # if set, POST /api/demo/seed requires X-Admin-Token

    @property
    def resolved_llm_mode(self) -> Literal["live", "cache_only", "mock"]:
        if self.llm_mode == "auto":
            return "live" if (self.google_api_key or self.use_vertexai) else "mock"
        return self.llm_mode

    def export_genai_env(self) -> None:
        """ADK's Gemini wrapper reads credentials from the process environment."""
        if self.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", self.google_api_key)
        if self.use_vertexai:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
            if self.gcp_project:
                os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.gcp_project)
            os.environ.setdefault("GOOGLE_CLOUD_LOCATION", self.vertex_location)
        else:
            os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.export_genai_env()
    return s
