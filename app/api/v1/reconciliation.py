"""
Reconciliation API - Summary metrics and discrepancy detection.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Literal
from datetime import datetime
import logging

from app.core.database import get_db
from app.schemas.reconciliation import (
    ReconciliationSummaryResponse,
    DiscrepancyListResponse,
)
from app.services.reconciliation_service import ReconciliationService

logger = logging.getLogger(__name__)

router = APIRouter()


DISCREPANCY_TYPES = Literal[
    "processed_not_settled",
    "settled_after_failure",
    "duplicate_settlement",
    "missing_initiation",
    "conflicting_events",
]


@router.get(
    "/summary",
    response_model=ReconciliationSummaryResponse,
    summary="Get reconciliation summary",
)
def get_reconciliation_summary(
    merchant_id: Optional[str] = Query(None, min_length=1, max_length=50),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    group_by: Literal["merchant", "date", "status", "merchant_status"] = Query("merchant"),
    db: Session = Depends(get_db),
):
    """Get aggregated reconciliation metrics grouped by specified dimension."""
    try:
        service = ReconciliationService(db)
        return service.get_summary(
            merchant_id=merchant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get(
    "/discrepancies",
    response_model=DiscrepancyListResponse,
    summary="Get reconciliation discrepancies",
)
def get_discrepancies(
    merchant_id: Optional[str] = Query(None, min_length=1, max_length=50),
    discrepancy_type: Optional[DISCREPANCY_TYPES] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Detect transactions with reconciliation issues.
    
    Discrepancy types: processed_not_settled, settled_after_failure,
    duplicate_settlement, missing_initiation, conflicting_events.
    """
    try:
        service = ReconciliationService(db)
        return service.get_discrepancies(
            merchant_id=merchant_id,
            discrepancy_type=discrepancy_type,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
