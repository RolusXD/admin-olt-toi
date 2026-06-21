from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _resolve_database_url() -> str:
  """Return the database URL giving precedence to the DATABASE_URL env var.

  This avoids importing PostgreSQL/psycopg drivers in test environments where
  a lightweight SQLite URL is provided explicitly via the DATABASE_URL
  environment variable (e.g. ``sqlite+pysqlite:///:memory:``), while keeping
  the existing PostgreSQL default for Docker/production when the env var is
  absent.
  """

  env_url = os.getenv("DATABASE_URL")
  if env_url:
      return env_url
  return settings.database_url


engine = create_engine(_resolve_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
