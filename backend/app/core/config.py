from pathlib import Path
from pydantic_settings import BaseSettings

# backend/.env, found relative to this file rather than the current folder
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    UPLOAD_DIR: str = "./data/uploads"
    DOCUAUDIT_SECRET: str = ""      # signs login tokens; the API refuses to start without it

    class Config:
        env_file = str(ENV_FILE)
        extra = "ignore"


settings = Settings()
