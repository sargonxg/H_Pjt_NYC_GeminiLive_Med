"""
CONCORDIA Configuration

Centralized settings via Pydantic Settings, all configurable via environment variables.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": True}

    # API & Model
    GOOGLE_API_KEY: str = ""
    CONCORDIA_MODEL: str = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Multi-party limits
    MAX_PARTIES_PER_CASE: int = Field(default=6, ge=2, le=20)

    # Health thresholds
    HEALTH_THRESHOLD_PARTY: int = Field(default=60, ge=0, le=100)
    HEALTH_THRESHOLD_RESOLVE: int = Field(default=75, ge=0, le=100)

    # Server
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "*"  # Comma-separated origins, or "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for app settings."""
    return Settings()
