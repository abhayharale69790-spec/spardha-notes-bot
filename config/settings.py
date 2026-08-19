"""Production Application Settings with Pydantic v2 BaseSettings."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Hardened configuration loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Telegram Bot Token
    bot_token: str = Field(
        default="123456789:TEST_MOCK_TOKEN_FOR_DEV",
        description="Telegram bot token obtained from @BotFather",
    )

    # Channel IDs (can be negative integer e.g. -1001234567890 or @username)
    main_channel_id: Union[int, str] = Field(
        default=-1001234567890,
        description="Public Telegram channel where approved materials are broadcast",
    )
    staging_channel_id: Union[int, str] = Field(
        default=-1009876543210,
        description="Private Telegram channel where scraper drafts are reviewed",
    )
    backup_channel_id: Union[int, str] = Field(
        default=-1001122334455,
        description="Private Telegram channel for automated disaster recovery database dumps",
    )

    # Admin User IDs
    admin_user_ids: List[int] = Field(
        default_factory=list,
        description="List of Telegram user IDs permitted to approve/discard drafts and manage the bot",
    )

    # Database URL (PostgreSQL asyncpg or SQLite aiosqlite fallback)
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/study_platform.db",
        validation_alias="DATABASE_URL",
        description="Async database connection string",
    )

    # Secondary alias check for DB_URL
    db_url: Optional[str] = Field(
        default=None,
        validation_alias="DB_URL",
        description="Alternative alias for database connection string",
    )

    # Gemini AI API Key for Semantic Search & Summarization
    gemini_api_key: Optional[str] = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
        description="Google AI Studio Gemini API Key for semantic embeddings and notice summarization",
    )

    # Redis Connection URL (Optional for distributed caching/throttling)
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL for distributed rate-limiting and queues",
    )

    # Interval Timers
    scrape_interval_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Frequency in minutes to scrape government & exam portals",
    )
    backup_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Frequency in hours to generate and upload automated database backups",
    )

    # Rate Limiting & Throttling (Optimized for smooth student navigation)
    rate_limit_rate: float = Field(
        default=5.0,
        description="Max requests per second allowed per user before throttling",
    )
    rate_limit_burst: int = Field(
        default=15,
        description="Burst tolerance capacity for user commands",
    )
    broadcast_rate_limit: float = Field(
        default=20.0,
        description="Max messages per second sent to channels to respect Telegram broadcast limits (max 30)",
    )

    # Storage
    download_dir: Path = Field(
        default=Path("downloads"),
        description="Local directory path for caching downloaded PDFs",
    )
    backup_dir: Path = Field(
        default=Path("backups"),
        description="Local directory path for temporary database backup dumps",
    )

    # User-agent header list for rotation
    user_agents: List[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        ],
        description="Rotated user agents to prevent scraper IP blocks",
    )

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, List[int], int]) -> List[int]:
        """Support comma-separated strings or integers in ADMIN_USER_IDS."""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(uid.strip()) for uid in v.split(",") if uid.strip().isdigit()]
        elif isinstance(v, int):
            return [v]
        elif isinstance(v, list):
            return [int(i) for i in v]
        return []

    def get_effective_db_url(self) -> str:
        """Resolve either DATABASE_URL or DB_URL with preference to DATABASE_URL."""
        return self.database_url or self.db_url or "sqlite+aiosqlite:///data/study_platform.db"


@lru_cache()
def get_settings() -> Settings:
    """Return cached instance of validated settings."""
    return Settings()
