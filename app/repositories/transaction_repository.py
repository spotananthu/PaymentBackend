"""
Transaction Repository - Data access layer for transactions.

All filtering, pagination, and sorting is performed in SQL for efficiency.
"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, desc, asc
from sqlalchemy.exc import IntegrityError
import logging

from app.models.entities import Transaction, TransactionStatus, Merchant, Event

logger = logging.getLogger(__name__)

ALLOWED_SORT_FIELDS = {"created_at", "updated_at", "amount", "status", "merchant_id"}


class TransactionRepository:
    """
    Repository for Transaction data access.
    
    All queries use SQL-level filtering and pagination for optimal performance.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        return self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    def get_by_id_with_details(self, transaction_id: str) -> Optional[Transaction]:
        """
        Get transaction with merchant eagerly loaded.
        
        Uses joinedload for efficient single-query fetch of transaction + merchant.
        """
        return (
            self.db.query(Transaction)
            .options(joinedload(Transaction.merchant))
            .filter(Transaction.id == transaction_id)
            .first()
        )
    
    def get_by_id_with_full_details(self, transaction_id: str) -> Optional[Transaction]:
        """
        Get transaction with merchant AND events eagerly loaded in a single query.
        """
        return (
            self.db.query(Transaction)
            .options(
                # JOIN for merchant (to-one relationship)
                joinedload(Transaction.merchant),
                # Separate IN query for events (to-many relationship)
                selectinload(Transaction.events),
            )
            .filter(Transaction.id == transaction_id)
            .first()
        )
    
    def exists(self, transaction_id: str) -> bool:
        """Check if transaction exists."""
        return self.db.query(
            self.db.query(Transaction).filter(Transaction.id == transaction_id).exists()
        ).scalar()
    
    def create(self, transaction: Transaction) -> Transaction:
        """Create a new transaction."""
        self.db.add(transaction)
        self.db.flush()
        return transaction
    
    def update_status(
        self,
        transaction_id: str,
        new_status: TransactionStatus,
    ) -> Optional[Transaction]:
        """Update transaction status."""
        transaction = self.get_by_id(transaction_id)
        if transaction:
            transaction.status = new_status
            transaction.updated_at = datetime.utcnow()
            self.db.flush()
        return transaction
    
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
    ) -> Tuple[List[Transaction], int]:
        """
        List transactions with SQL-based filtering, pagination, and sorting.
        """
        # Build base query
        query = self.db.query(Transaction)
        
        # Apply filters (all done in SQL)
        query = self._apply_filters(query, merchant_id, status, start_date, end_date)
        
        # Get total count with same filters (single COUNT query)
        total_count = query.count()
        
        # Apply sorting (validated against whitelist)
        query = self._apply_sorting(query, sort_by, sort_order)
        
        # Apply pagination (LIMIT/OFFSET in SQL)
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        transactions = query.all()
        
        logger.debug(
            f"Listed transactions: filters(merchant={merchant_id}, status={status}), "
            f"page={page}, total={total_count}"
        )
        
        return transactions, total_count
    
    def _apply_filters(
        self,
        query,
        merchant_id: Optional[str],
        status: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ):
        """Apply WHERE clauses for filtering."""
        
        # Filter by merchant_id (uses ix_transactions_merchant_id index)
        if merchant_id:
            query = query.filter(Transaction.merchant_id == merchant_id)
        
        # Filter by status (uses ix_transactions_status index)
        if status:
            try:
                status_enum = TransactionStatus(status.lower())
                query = query.filter(Transaction.status == status_enum)
            except ValueError:
                logger.warning(f"Invalid status filter ignored: {status}")
                # Invalid status - don't apply filter (or could raise error)
        
        # Filter by date range (uses ix_transactions_created_at index)
        if start_date:
            query = query.filter(Transaction.created_at >= start_date)
        
        if end_date:
            query = query.filter(Transaction.created_at <= end_date)
        
        return query
    
    def _apply_sorting(
        self,
        query,
        sort_by: str,
        sort_order: str,
    ):
        """Apply ORDER BY clause with validation."""
        
        # Validate sort field (prevent SQL injection)
        if sort_by not in ALLOWED_SORT_FIELDS:
            logger.warning(f"Invalid sort field '{sort_by}', defaulting to created_at")
            sort_by = "created_at"
        
        # Get column reference
        sort_column = getattr(Transaction, sort_by, Transaction.created_at)
        
        # Apply sort direction
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        return query
    
    def count_by_merchant(self, merchant_id: str) -> int:
        """Count transactions for a merchant."""
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.merchant_id == merchant_id)
            .scalar()
        )
    
    def count_by_status(self, status: TransactionStatus) -> int:
        """Count transactions by status."""
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.status == status)
            .scalar()
        )
    
    def get_transactions_by_ids(self, transaction_ids: List[str]) -> List[Transaction]:
        """Get multiple transactions by IDs."""
        if not transaction_ids:
            return []
        return (
            self.db.query(Transaction)
            .filter(Transaction.id.in_(transaction_ids))
            .all()
        )
