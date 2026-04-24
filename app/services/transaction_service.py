"""
Transaction Service - Transaction queries with filtering and pagination.
"""

from typing import Optional, List
from datetime import datetime
import math

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, desc, asc

from app.models.entities import Transaction, Merchant
from app.schemas.transaction import (
    TransactionResponse,
    TransactionDetailResponse,
    TransactionListResponse,
    MerchantInfo,
)
from app.schemas.event import EventSummary
from app.schemas.common import PaginationMeta


class TransactionService:
    """Handles transaction queries with filtering, pagination, and sorting."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def list_transactions(
        self,
        merchant_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> TransactionListResponse:
        """List transactions with SQL-based filtering and pagination."""
        
        # Build base query
        query = select(Transaction)
        count_query = select(func.count(Transaction.id))
        
        # Apply filters
        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
            count_query = count_query.where(Transaction.merchant_id == merchant_id)
        if status:
            query = query.where(Transaction.status == status)
            count_query = count_query.where(Transaction.status == status)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
            count_query = count_query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)
            count_query = count_query.where(Transaction.created_at <= end_date)
        
        # Get total count
        total_count = self.db.execute(count_query).scalar() or 0
        
        # Apply sorting
        sort_column = getattr(Transaction, sort_by, Transaction.created_at)
        query = query.order_by(desc(sort_column) if sort_order == "desc" else asc(sort_column))
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        transactions = self.db.execute(query).scalars().all()
        
        # Build response
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        return TransactionListResponse(
            transactions=[self._to_response(t) for t in transactions],
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total_count,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
        )
    
    def get_transaction_detail(self, transaction_id: str) -> Optional[TransactionDetailResponse]:
        """Get transaction with merchant and events (eager loaded to avoid N+1)."""
        
        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.merchant),
                selectinload(Transaction.events),
            )
            .where(Transaction.id == transaction_id)
        )
        
        transaction = self.db.execute(query).scalar_one_or_none()
        if not transaction:
            return None
        
        # Sort events by timestamp
        sorted_events = sorted(transaction.events, key=lambda e: e.timestamp)
        
        return TransactionDetailResponse(
            transaction_id=transaction.id,
            merchant=MerchantInfo(
                id=transaction.merchant.id,
                name=transaction.merchant.name,
            ),
            amount=float(transaction.amount),
            currency=transaction.currency,
            status=transaction.status.value,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
            event_count=len(sorted_events),
            events=[
                EventSummary(
                    event_id=e.id,
                    event_type=e.event_type.value,
                    timestamp=e.timestamp,
                )
                for e in sorted_events
            ],
        )
    
    def _to_response(self, transaction: Transaction) -> TransactionResponse:
        return TransactionResponse(
            transaction_id=transaction.id,
            merchant_id=transaction.merchant_id,
            amount=float(transaction.amount),
            currency=transaction.currency,
            status=transaction.status.value,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
        )
