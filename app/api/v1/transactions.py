"""
Transactions API - Query and retrieve transaction data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Literal
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.config import settings
from app.schemas.transaction import (
    TransactionResponse,
    TransactionDetailResponse,
    TransactionListResponse,
)
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions with filters",
)
def list_transactions(
    merchant_id: Optional[str] = Query(None),
    status: Optional[Literal["initiated", "processed", "failed", "settled"]] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    sort_by: Literal["created_at", "updated_at", "amount", "status"] = Query("created_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    """List transactions with optional filtering and pagination."""
    try:
        if page_size is None:
            page_size = settings.DEFAULT_PAGE_SIZE
        
        service = TransactionService(db)
        return service.list_transactions(
            merchant_id=merchant_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetailResponse,
    summary="Get transaction details",
)
def get_transaction(
    transaction_id: str = Path(...),
    db: Session = Depends(get_db),
) -> TransactionDetailResponse:
    """Get transaction details with event history."""
    try:
        service = TransactionService(db)
        result = service.get_transaction_detail(transaction_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")
        
        return result
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
