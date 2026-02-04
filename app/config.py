from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration (env-friendly).

    Tip: create a .env file (it is already in .gitignore) and override settings there.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Accessibility Finder API"
    version: str = "0.1.0"

    nominatim_base_url: AnyHttpUrl = "https://nominatim.openstreetmap.org/search"
    overpass_base_url: AnyHttpUrl = "https://overpass-api.de/api/interpreter"

    # Nominatim's usage policy expects a proper User-Agent and (optionally) contact info.
    user_agent: str = "accessibility-finder/0.1.0 (github.com/DenisTkachenko888/accessibility-finder)"
    nominatim_email: Optional[str] = None

    http_timeout_s: float = 20.0

    cache_ttl_s: float = 120.0
    cache_max_size: int = 512


@lru_cache
def get_settings() -> Settings:
    return Settings()
