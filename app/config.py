import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PORTAL_BASE_URL: str = os.getenv("PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")
    PORTAL_USERNAME: str = os.getenv("PORTAL_USERNAME", "operator@urja.local")
    PORTAL_PASSWORD: str = os.getenv("PORTAL_PASSWORD", "urja-ops-2026")
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "15.0"))

settings = Settings()
