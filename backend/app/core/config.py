from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "VaidyaScribe"
    DEBUG: bool = False
    SECRET_KEY: str = "vaidyascribe-jwt-secret-change-in-production-2026"

    # ── CORS ──────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    # ── Database ───────────────────────────────────────────────────
    # Local:  sqlite+aiosqlite:///./data/vaidyascribe.db
    # AWS:    postgresql+asyncpg://user:pass@rds-endpoint:5432/vaidyascribe
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/vaidyascribe.db"
    LANCEDB_URI: str = "./data/lancedb"

    # ── Redis ──────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Ollama ─────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # ── Groq ───────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    USE_GROQ_FALLBACK: bool = False

    # ── Whisper ────────────────────────────────────────────────────
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # ── NLLB ───────────────────────────────────────────────────────
    NLLB_MODEL: str = "facebook/nllb-200-distilled-600M"

    # ── QA + burnout thresholds ────────────────────────────────────
    QA_CONFIDENCE_THRESHOLD: float = 0.70
    BURNOUT_HOURS_THRESHOLD: float = 10.0
    BURNOUT_NOTES_THRESHOLD: int = 50

    # ── AWS S3 (free tier — 5GB) ───────────────────────────────────
    # Leave empty to use local file storage (default for local dev)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"          # Mumbai — closest to India
    S3_BUCKET_NAME: str = ""                 # e.g. vaidyascribe-exports

    @property
    def use_s3(self) -> bool:
        return bool(self.AWS_ACCESS_KEY_ID and self.S3_BUCKET_NAME)

    @property
    def use_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")


settings = Settings()
