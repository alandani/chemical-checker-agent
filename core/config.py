"""Application settings, read from environment variables or a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    # Storage
    database_url: str = f"sqlite:///{DATA_DIR / 'chemchecker.db'}"

    # Claude
    anthropic_api_key: str | None = None
    claude_model_reasoning: str = "claude-sonnet-5-5"
    claude_model_extraction: str = "claude-haiku-5-5"

    # Pricing
    base_currency: str = "AUD"
    offer_max_age_days: int = 7
    enable_live_scraping: bool = True
    scrape_timeout_s: int = 30
    # Comma-separated vendor keys to scrape (see scrapers/vendors.py)
    enabled_vendors: str = "bldpharm,enamine,medchemexpress"

    # Routes
    aizynth_config: str | None = None  # path to AiZynthFinder config.yml
    aizynth_time_limit_s: int = 90

    # Network
    http_timeout_s: int = 20
    user_agent: str = "ChemPriceChecker/0.1 (research prototype)"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def enabled_vendor_keys(self) -> list[str]:
        return [v.strip() for v in self.enabled_vendors.split(",") if v.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
