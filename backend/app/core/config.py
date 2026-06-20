from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TOI OLT Manager"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://toi_olt:toi_olt@localhost:5432/toi_olt_manager"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    crypto_key: str = "change-me-32-byte-secret-for-prod"
    admin_username: str | None = None
    admin_password_hash: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
