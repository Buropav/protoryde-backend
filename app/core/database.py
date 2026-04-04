import logging
import os
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


# Use DATABASE_URL when provided. Fall back to local SQLite to keep demo setup reliable.
SQLALCHEMY_DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./protoryde.db"))
CONNECT_ARGS = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=CONNECT_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_MAX_RETRIES = 5
_INITIAL_BACKOFF_S = 2


def init_db():
    """Create tables, retrying on transient DB connection failures (e.g. Render Postgres not ready yet)."""
    from app.core import models  # noqa: F401

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully.")
            return
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                logger.error("Database connection failed after %d attempts: %s", _MAX_RETRIES, exc)
                raise
            wait = _INITIAL_BACKOFF_S * (2 ** (attempt - 1))
            logger.warning("DB connection attempt %d/%d failed (%s). Retrying in %ds...", attempt, _MAX_RETRIES, exc, wait)
            time.sleep(wait)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
