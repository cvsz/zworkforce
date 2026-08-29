import os
from pydantic import BaseModel

class Settings(BaseModel):
    app_name: str = "zider Backend Gateway"
    version: str = "1.0.0"
    host: str = os.getenv("ZIDER_HOST", "0.0.0.0")
    port: int = int(os.getenv("ZIDER_PORT", "8085"))
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    upload_dir: str = os.getenv("ZIDER_UPLOAD_DIR", "/tmp/zider_uploads")
    allowed_origins: list[str] = [
        o.strip()
        for o in os.getenv("ZIDER_ALLOWED_ORIGINS", "https://zider.zeaz.dev,http://localhost:*").split(",")
        if o.strip()
    ]

settings = Settings()
os.makedirs(settings.upload_dir, exist_ok=True)
