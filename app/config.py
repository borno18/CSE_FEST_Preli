import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GEMINI_API_KEY: str = ""
    HIGH_VALUE_THRESHOLD: float = 20000.0
    PORT: int = 8000
    FRONTEND_ORIGIN: str = "*"

# Load settings
settings = Settings()

# ALWAYS prioritize system environment variables directly (overriding the .env file if set in Render/Vercel)
env_key = os.environ.get("GEMINI_API_KEY")
if env_key:
    settings.GEMINI_API_KEY = env_key

# Fail loudly on startup if GEMINI_API_KEY is missing
if not settings.GEMINI_API_KEY:
    raise ValueError(
        "CRITICAL STARTUP ERROR: GEMINI_API_KEY is not set in environment variables or .env file."
    )
