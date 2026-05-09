"""
config.py — All application settings loaded from environment variables.
Supports local .env file via python-dotenv and production env vars for cloud deployments.
"""
import os
import secrets
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _get_secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if not key:
        key = secrets.token_hex(32)
        logger.warning(
            "SECRET_KEY not set in environment — using a randomly generated key. "
            "Sessions will be invalidated on every restart. Set SECRET_KEY in .env for persistence."
        )
    return key


class Settings:
    # App
    APP_NAME: str = os.getenv("APP_NAME", "CSP Analyzer")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database — SQLite locally, swap to PostgreSQL URL for cloud
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./csp_analyzer.db")

    # Session / security
    SECRET_KEY: str = _get_secret_key()
    SESSION_MAX_AGE: int = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))  # 7 days

    # Default admin credentials (first-run only — prompt user to change immediately)
    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASS: str = os.getenv("DEFAULT_ADMIN_PASS", "admin123")
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@localhost")

    # Background scheduler — how often to refresh open-position prices (seconds)
    PRICE_REFRESH_INTERVAL: int = int(os.getenv("PRICE_REFRESH_INTERVAL", "300"))

    # AI Configuration (DeepSeek)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")


settings = Settings()
