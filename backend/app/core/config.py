import ipaddress
import os
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Search for .env in current directory or project root
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_paths = [
    root_dir / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break
else:
    load_dotenv()


def parse_allowed_origins(raw_origins: str) -> List[str]:
    """
    Parses comma-separated CORS origins and rejects wildcard '*' entries
    so credentialed cross-origin rules always fail closed if misconfigured.
    """
    origins: List[str] = []
    for item in raw_origins.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        if origin == "*":
            logger.warning("Ignoring wildcard '*' in ALLOWED_ORIGINS for CORS security hardening.")
            continue
        origins.append(origin)
    return origins


def parse_trusted_proxy_cidrs(raw_cidrs: str) -> List[ipaddress._BaseNetwork]:
    """Parses comma-separated CIDR/IP networks trusted to assert forwarded client IP headers."""
    networks: List[ipaddress._BaseNetwork] = []
    for item in raw_cidrs.split(","):
        val = item.strip()
        if not val:
            continue
        try:
            networks.append(ipaddress.ip_network(val, strict=False))
        except ValueError:
            logger.warning(f"Ignoring malformed TRUSTED_PROXY_CIDRS entry: {val}")
    return networks


class Settings:
    PROJECT_NAME: str = "BreatheWise AI"
    VERSION: str = "1.2"
    
    # Air Quality Provider Keys
    WAQI_API_TOKEN: str = os.getenv("WAQI_API_TOKEN", "").strip()
    OPENAQ_API_KEY: str = os.getenv("OPENAQ_API_KEY", "").strip()
    
    # Generative AI Models (Configurable via Environment Variables)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL_ID: str = os.getenv("GROQ_MODEL_ID", "llama-3.3-70b-versatile").strip()
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL_ID: str = os.getenv("GEMINI_MODEL_ID", "gemini-1.5-flash").strip()
    
    # Cache and Freshness Thresholds
    AIR_DATA_CACHE_TTL_SECONDS: int = int(os.getenv("AIR_DATA_CACHE_TTL_SECONDS", "1800"))
    GROUND_DATA_FRESHNESS_HOURS: int = 3

    # AI Planner Rate Limiting & Trusted Proxy Boundary
    RATE_LIMIT_PLAN_REQUESTS: int = int(os.getenv("RATE_LIMIT_PLAN_REQUESTS", "10"))
    RATE_LIMIT_PLAN_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_PLAN_WINDOW_SECONDS", "60"))
    RATE_LIMIT_MAX_TRACKED_KEYS: int = int(os.getenv("RATE_LIMIT_MAX_TRACKED_KEYS", "2048"))
    TRUST_PROXY_HEADERS: bool = os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower() == "true"
    TRUSTED_PROXY_CIDRS: List[ipaddress._BaseNetwork] = parse_trusted_proxy_cidrs(
        os.getenv("TRUSTED_PROXY_CIDRS", "")
    )
    
    # Server & CORS
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    ALLOWED_ORIGINS: List[str] = parse_allowed_origins(
        os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    )


settings = Settings()
