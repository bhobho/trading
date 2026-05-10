"""
database.py — SQLAlchemy engine, session factory, and Base declarative class.

Uses connect_args={"check_same_thread": False} only for SQLite (required because
FastAPI handles requests across multiple threads). PostgreSQL does not need this.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

# SQLite needs check_same_thread=False; PostgreSQL does not.
_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    # pool_pre_ping keeps the connection healthy across long idle periods (important for cloud)
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
