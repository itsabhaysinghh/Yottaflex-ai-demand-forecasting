import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Determine connection pool settings based on database dialect
is_sqlite = settings.effective_database_url.startswith("sqlite")

engine_kwargs = {
    "echo": settings.DEBUG and settings.ENVIRONMENT == "development",
}

if not is_sqlite:
    # PostgreSQL connection pooling optimizations
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    })
else:
    # SQLite connection configuration
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.effective_database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a request-scoped database session
    and ensures proper closing on completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

