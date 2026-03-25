from __future__ import annotations
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "HeyStat Classroom API"
    debug: bool = False
    secret_key: str = "change-me-in-production-use-secrets-token-hex-32"

    # JWT
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # Database
    database_url: str = "postgresql+asyncpg://heystat:heystat@localhost:5432/classroom"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS – set in .env as JSON array: ["https://example.com"]
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:80"]

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Sync DB URL (for Celery workers)
    sync_database_url: str = "postgresql+psycopg2://heystat:heystat@localhost:5432/classroom"
    
    # File storage
    upload_dir: str = "/root/Documents/uploads"
    max_file_size_mb: int = 50
    max_user_files: int = 100
    max_user_storage_mb: int = 500
    
    # Email (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: str = "noreply@heystat.pedu.vn"
    
    # HeyStat
    heystat_base_url: str = "http://localhost:42337"
    jamovi_data_root: str = "/root/Documents"
    # Shared with HeyStat container for collab_role token verification (Phase 10)
    jamovi_collab_secret: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
