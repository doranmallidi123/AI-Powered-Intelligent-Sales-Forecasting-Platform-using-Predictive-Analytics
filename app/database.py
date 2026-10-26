"""SQLAlchemy engine and request-scoped database session dependency."""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

# Load variables from the project .env when present; existing process variables
# take precedence, as expected in containers and production deployments.
load_dotenv()

_database_url = os.getenv("DATABASE_URL")
if not _database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Configure it in the environment or a .env file."
    )

_url = make_url(_database_url)
_connect_args = {"check_same_thread": False} if _url.get_backend_name() == "sqlite" else {}

engine = create_engine(
    _url,
    pool_pre_ping=True,
    # SQLite uses its own pool implementation; these options apply to PostgreSQL
    # and other server databases.
    **({"pool_size": 5, "max_overflow": 10} if _url.get_backend_name() != "sqlite" else {}),
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield one session per request and always close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
