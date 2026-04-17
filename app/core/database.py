import logging
import os
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


# Use DATABASE_URL when provided. Fall back to local SQLite to keep demo setup reliable.
SQLALCHEMY_DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./protoryde.db")
)
CONNECT_ARGS = (
    {"check_same_thread": False, "timeout": 30}
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=CONNECT_ARGS,
    pool_pre_ping=True,  # Auto-reconnect stale/dead connections
)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout = 30000;")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_MAX_RETRIES = 8
_INITIAL_BACKOFF_S = 3


def init_db():
    """Create tables, retrying on transient DB connection failures.

    On Render free tier, Postgres can take several minutes to provision.
    If all retries fail, the app still starts — the health endpoint works
    immediately, and DB-dependent endpoints will connect once Postgres is ready
    (thanks to pool_pre_ping).
    """
    from app.core import models  # noqa: F401

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully.")
            return
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                logger.error(
                    "Database unavailable after %d attempts (%s). "
                    "App will start anyway — tables will be created on first successful connection.",
                    _MAX_RETRIES,
                    exc,
                )
                return  # Don't crash — let the app start
            wait = _INITIAL_BACKOFF_S * (2 ** (attempt - 1))
            logger.warning(
                "DB connection attempt %d/%d failed (%s). Retrying in %ds...",
                attempt,
                _MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
