"""
Database configuration and session management.
Uses SQLAlchemy for ORM and raw SQL capabilities.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Create database engine using the sync-compatible URL
engine = create_engine(
    settings.database_url_sync,
    pool_pre_ping=True,  # Verify connections before use
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    Database session dependency for FastAPI.
    Yields a database session and ensures cleanup after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
