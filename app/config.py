"""
Purpose: Central configuration for the Tax365 Telegram application.
Sample input: Environment variables from .env.
Output: A validated Settings object containing paths and integration settings.
Dependencies: pathlib, os, python-dotenv.
Architecture: Telegram -> Python configuration -> database / AnythingLLM / artifact services.
"""

from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

def _project_path(value: str, default: str) -> Path:
    """Resolve a configured path relative to the project root unless it is absolute."""
    candidate = Path(value or default).expanduser()
    return candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()

@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""
    telegram_bot_token: str
    allowed_telegram_user_ids: set[int]
    data_dir: Path
    database_path: Path
    artifacts_dir: Path
    log_dir: Path
    anythingllm_enabled: bool
    anythingllm_base_url: str
    anythingllm_api_key: str
    anythingllm_workspace_slug: str
    anythingllm_timeout_seconds: float
    organization_name: str

def load_settings() -> Settings:
    """
    Build and validate application settings.
    Input: .env / process environment.
    Output: Settings instance. Raises ValueError for missing required credentials.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    raw_ids = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
    allowed_ids = {int(item.strip()) for item in raw_ids.split(",") if item.strip()}
    enabled = os.getenv("ANYTHINGLLM_ENABLED", "false").lower() == "true"
    api_key = os.getenv("ANYTHINGLLM_API_KEY", "").strip()
    if enabled and not api_key:
        raise ValueError("ANYTHINGLLM_ENABLED=true but ANYTHINGLLM_API_KEY is empty.")
    return Settings(
        telegram_bot_token=token,
        allowed_telegram_user_ids=allowed_ids,
        data_dir=_project_path(os.getenv("DATA_DIR", "../data"), "../data"),
        database_path=_project_path(os.getenv("DATABASE_PATH", "database/tax365.db"), "database/tax365.db"),
        artifacts_dir=_project_path(os.getenv("ARTIFACTS_DIR", "artifacts"), "artifacts"),
        log_dir=_project_path(os.getenv("LOG_DIR", "logs"), "logs"),
        anythingllm_enabled=enabled,
        anythingllm_base_url=os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001").rstrip("/"),
        anythingllm_api_key=api_key,
        anythingllm_workspace_slug=os.getenv("ANYTHINGLLM_WORKSPACE_SLUG", "global-tax-intelligence"),
        anythingllm_timeout_seconds=float(os.getenv("ANYTHINGLLM_TIMEOUT_SECONDS", "45")),
        organization_name=os.getenv("ORGANIZATION_NAME", "Illustrative Global Agri-Food Group"),
    )
