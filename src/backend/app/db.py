"""Database engine, session factory and declarative base.

SQLite is used for zero-setup local runs. We enable WAL mode and a busy timeout so
concurrent writers (e.g. two analysts claiming detections) serialize cleanly at the
database level instead of failing with "database is locked".
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# check_same_thread=False: FastAPI serves requests from a threadpool; a single SQLite
# connection may be touched by different threads. Safe here because SQLAlchemy pools
# per-connection and we never share a Session across threads.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    """Harden SQLite for concurrent access."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")       # readers don't block the writer
    cursor.execute("PRAGMA busy_timeout=5000")      # wait up to 5s for a lock
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
