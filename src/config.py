import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "Support Ticket AI Intelligence System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    CSV_PATH: Path = BASE_DIR / "support_tickets.csv"
    DB_PATH: Path = BASE_DIR / "data" / "support_tickets.db"
    TEMPLATES_DIR: Path = BASE_DIR / "src" / "templates"
    STATIC_DIR: Path = BASE_DIR / "src" / "static"

    # LLM Settings
    LLM_PROVIDER: str = "auto"  # 'auto', 'groq', 'ollama', 'fallback'
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # Anomaly Thresholds
    ANOMALY_IQR_MULTIPLIER: float = 1.5
    ANOMALY_SLA_URGENT_HOURS: float = 24.0
    ANOMALY_LOW_RATING_THRESHOLD: int = 2

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
