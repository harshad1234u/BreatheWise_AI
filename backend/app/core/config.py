import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

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
    
    # Server & CORS
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    ALLOWED_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]


settings = Settings()
