"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter()


@router.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "payment-reconciliation"}


@router.get("/health/db")
def database_health_check(db: Session = Depends(get_db)):
    """Database connectivity health check."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
