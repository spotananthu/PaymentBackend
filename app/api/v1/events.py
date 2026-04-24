"""
Events API - Payment lifecycle event ingestion.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.core.database import get_db
from app.schemas.event import EventCreate, EventResponse, EventBulkCreate, BulkIngestResponse
from app.services.event_service import EventService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a payment event (idempotent)",
)
def ingest_event(
    event: EventCreate,
    db: Session = Depends(get_db),
) -> EventResponse:
    """Ingest a single payment event. Duplicate event_ids return is_duplicate=true."""
    try:
        service = EventService(db)
        return service.ingest_event(event)
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


@router.post(
    "/bulk",
    response_model=BulkIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk ingest events (10k+ optimized)",
)
def ingest_events_bulk(
    payload: EventBulkCreate,
    db: Session = Depends(get_db),
) -> BulkIngestResponse:
    """Bulk ingest events with duplicate detection and batch processing."""
    try:
        service = EventService(db)
        return service.ingest_events_bulk(payload.events)
    except SQLAlchemyError as e:
        logger.error(f"Database error in bulk ingest: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in bulk ingest: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")
