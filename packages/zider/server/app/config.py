import os
from typing import List
from pydantic import BaseModel


def _parse_cors_origins(raw: str) -> List[str]:
    origins = [item.strip() for item in (raw or "").split(",") if item.strip()]
    if "*" in origins:
        raise ValueError("ZIDER_CORS_ORIGINS must not contain wildcard '*'")
    return origins


class Settings(BaseModel):
    app_name: str = "zider Backend Gateway"
    version: str = "1.0.0"
    host: str = os.getenv("ZIDER_HOST", "127.0.0.1")
    port: int = int(os.getenv("ZIDER_PORT", "8085"))
    cors_origins: List[str] = _parse_cors_origins(os.getenv("ZIDER_CORS_ORIGINS", ""))
    api_token: str = os.getenv("ZIDER_API_TOKEN", "")
    require_auth: bool = os.getenv("ZIDER_REQUIRE_AUTH", "").strip().lower() in ("1", "true", "yes")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    upload_dir: str = os.getenv("ZIDER_UPLOAD_DIR", "/tmp/zider_uploads")


settings = Settings()
os.makedirs(settings.upload_dir, exist_ok=True)
