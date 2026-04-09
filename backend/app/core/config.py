from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "VaidyaScribe"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # ── CORS: cover every origin the browser can send ─────────────
    # http://localhost   → nginx on :80 (no port in URL bar)
    # http://localhost:80 → explicit
    # http://localhost:3000 → Vite dev server / frontend container
    # http://127.0.0.1   → some browsers use this instead of localhost
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:80",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    # Database — free SQLite
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/vaidyascribe.db"
    LANCEDB_URI: str = "./data/lancedb"

    # Redis — local Docker
    REDIS_URL: str = "redis://localhost:6379/0"

    # Ollama — free local LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Groq — free tier fallback (6000 tokens/min, no card)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    # Use Groq when Ollama is unavailable (set to true for fast demo)
    USE_GROQ_FALLBACK: bool = False

    # Whisper — local model
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # NLLB translation model — free HuggingFace
    NLLB_MODEL: str = "facebook/nllb-200-distilled-600M"

    # QA confidence threshold — below this triggers human review
    QA_CONFIDENCE_THRESHOLD: float = 0.70

    # Burnout — alert if weekly session hours exceed this
    BURNOUT_HOURS_THRESHOLD: float = 10.0
    BURNOUT_NOTES_THRESHOLD: int = 50


settings = Settings()
