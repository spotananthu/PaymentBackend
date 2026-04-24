"""
Reconciliation Service - Summary reports and discrepancy detection.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import math

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, case, and_, exists, cast, Date

from app.models.entities import Transaction, Event, Merchant, TransactionStatus, EventType
from app.schemas.reconciliation import (
    ReconciliationSummaryResponse,
    DiscrepancyListResponse,
    DiscrepancyItem,
    SummaryItem,
)
from app.schemas.event import EventSummary
from app.schemas.common import PaginationMeta


class ReconciliationService:
    """Handles reconciliation reporting and discrepancy detection."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ========== Summary Reports ==========
    
    def get_summary(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "merchant",
    ) -> ReconciliationSummaryResponse:
        """Get reconciliation summary with SQL GROUP BY aggregation."""
        
        if group_by == "status":
            summary = self._get_summary_by_status(merchant_id, start_date, end_date)
        elif group_by == "date":
            summary = self._get_summary_by_date(merchant_id, start_date, end_date)
        elif group_by == "merchant_status":
            summary = self._get_summary_by_merchant_status(merchant_id, start_date, end_date)
        else:  # Default: merchant
            summary = self._get_summary_by_merchant(merchant_id, start_date, end_date)
        
        totals = self._get_totals(merchant_id, start_date, end_date)
        
        period = None
        if start_date or end_date:
            period = {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            }
        
        return ReconciliationSummaryResponse(
            group_by=group_by,
            period=period,
            summary=summary,
            totals=totals,
            generated_at=datetime.utcnow(),
        )
    
    def _get_summary_by_merchant(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[SummaryItem]:
        """Group by merchant with status breakdown."""
        
        query = (
            select(
                Transaction.merchant_id,
                Merchant.name.label("merchant_name"),
                func.count(Transaction.id).label("total_transactions"),
                func.sum(Transaction.amount).label("total_amount"),
                func.sum(case((Transaction.status == TransactionStatus.SETTLED, 1), else_=0)).label("settled_count"),
                func.sum(case((Transaction.status == TransactionStatus.SETTLED, Transaction.amount), else_=0)).label("settled_amount"),
                func.sum(case((Transaction.status == TransactionStatus.PROCESSED, 1), else_=0)).label("processed_count"),
                func.sum(case((Transaction.status == TransactionStatus.PROCESSED, Transaction.amount), else_=0)).label("processed_amount"),
                func.sum(case((Transaction.status == TransactionStatus.FAILED, 1), else_=0)).label("failed_count"),
                func.sum(case((Transaction.status == TransactionStatus.FAILED, Transaction.amount), else_=0)).label("failed_amount"),
                func.sum(case((Transaction.status == TransactionStatus.INITIATED, 1), else_=0)).label("initiated_count"),
                func.sum(case((Transaction.status == TransactionStatus.INITIATED, Transaction.amount), else_=0)).label("initiated_amount"),
            )
            .join(Merchant, Transaction.merchant_id == Merchant.id)
            .group_by(Transaction.merchant_id, Merchant.name)
        )
        
        query = self._apply_filters(query, merchant_id, start_date, end_date)
        rows = self.db.execute(query).fetchall()
        
        return [
            SummaryItem(
                group_key=row.merchant_id,
                group_value=row.merchant_name,
                total_transactions=row.total_transactions,
                total_amount=float(row.total_amount or 0),
                settled_count=row.settled_count,
                settled_amount=float(row.settled_amount or 0),
                processed_count=row.processed_count,
                processed_amount=float(row.processed_amount or 0),
                failed_count=row.failed_count,
                failed_amount=float(row.failed_amount or 0),
                initiated_count=row.initiated_count,
                initiated_amount=float(row.initiated_amount or 0),
                settlement_rate=round((row.settled_count / row.total_transactions * 100), 2) if row.total_transactions > 0 else 0.0,
            )
            for row in rows
        ]
    
    def _get_summary_by_status(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[SummaryItem]:
        """Group by status only."""
        
        query = (
            select(
                Transaction.status,
                func.count(Transaction.id).label("total_transactions"),
                func.sum(Transaction.amount).label("total_amount"),
            )
            .group_by(Transaction.status)
        )
        
        query = self._apply_filters(query, merchant_id, start_date, end_date)
        rows = self.db.execute(query).fetchall()
        
        return [
            SummaryItem(
                group_key=row.status.value,
                group_value=row.status.value.title(),
                total_transactions=row.total_transactions,
                total_amount=float(row.total_amount or 0),
                settled_count=row.total_transactions if row.status == TransactionStatus.SETTLED else 0,
                settled_amount=float(row.total_amount or 0) if row.status == TransactionStatus.SETTLED else 0.0,
                processed_count=row.total_transactions if row.status == TransactionStatus.PROCESSED else 0,
                processed_amount=float(row.total_amount or 0) if row.status == TransactionStatus.PROCESSED else 0.0,
                failed_count=row.total_transactions if row.status == TransactionStatus.FAILED else 0,
                failed_amount=float(row.total_amount or 0) if row.status == TransactionStatus.FAILED else 0.0,
                initiated_count=row.total_transactions if row.status == TransactionStatus.INITIATED else 0,
                initiated_amount=float(row.total_amount or 0) if row.status == TransactionStatus.INITIATED else 0.0,
                settlement_rate=100.0 if row.status == TransactionStatus.SETTLED else 0.0,
            )
            for row in rows
        ]
    
    def _get_summary_by_date(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[SummaryItem]:
        """Group by transaction creation date."""

        txn_date = cast(Transaction.created_at, Date).label("txn_date")

        query = (
            select(
                txn_date,
                func.count(Transaction.id).label("total_transactions"),
                func.sum(Transaction.amount).label("total_amount"),
                func.sum(case((Transaction.status == TransactionStatus.SETTLED, 1), else_=0)).label("settled_count"),
                func.sum(case((Transaction.status == TransactionStatus.SETTLED, Transaction.amount), else_=0)).label("settled_amount"),
                func.sum(case((Transaction.status == TransactionStatus.PROCESSED, 1), else_=0)).label("processed_count"),
                func.sum(case((Transaction.status == TransactionStatus.PROCESSED, Transaction.amount), else_=0)).label("processed_amount"),
                func.sum(case((Transaction.status == TransactionStatus.FAILED, 1), else_=0)).label("failed_count"),
                func.sum(case((Transaction.status == TransactionStatus.FAILED, Transaction.amount), else_=0)).label("failed_amount"),
                func.sum(case((Transaction.status == TransactionStatus.INITIATED, 1), else_=0)).label("initiated_count"),
                func.sum(case((Transaction.status == TransactionStatus.INITIATED, Transaction.amount), else_=0)).label("initiated_amount"),
            )
            .group_by(txn_date)
            .order_by(txn_date)
        )

        query = self._apply_filters(query, merchant_id, start_date, end_date)
        rows = self.db.execute(query).fetchall()

        return [
            SummaryItem(
                group_key=str(row.txn_date),
                group_value=str(row.txn_date),
                total_transactions=row.total_transactions,
                total_amount=float(row.total_amount or 0),
                settled_count=row.settled_count,
                settled_amount=float(row.settled_amount or 0),
                processed_count=row.processed_count,
                processed_amount=float(row.processed_amount or 0),
                failed_count=row.failed_count,
                failed_amount=float(row.failed_amount or 0),
                initiated_count=row.initiated_count,
                initiated_amount=float(row.initiated_amount or 0),
                settlement_rate=round((row.settled_count / row.total_transactions * 100), 2) if row.total_transactions > 0 else 0.0,
            )
            for row in rows
        ]

    def _get_summary_by_merchant_status(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[SummaryItem]:
        """Group by merchant AND status combination."""

        query = (
            select(
                Transaction.merchant_id,
                Merchant.name.label("merchant_name"),
                Transaction.status,
                func.count(Transaction.id).label("total_transactions"),
                func.sum(Transaction.amount).label("total_amount"),
            )
            .join(Merchant, Transaction.merchant_id == Merchant.id)
            .group_by(Transaction.merchant_id, Merchant.name, Transaction.status)
            .order_by(Transaction.merchant_id, Transaction.status)
        )

        query = self._apply_filters(query, merchant_id, start_date, end_date)
        rows = self.db.execute(query).fetchall()

        return [
            SummaryItem(
                group_key=f"{row.merchant_id}_{row.status.value}",
                group_value=f"{row.merchant_name} - {row.status.value.title()}",
                total_transactions=row.total_transactions,
                total_amount=float(row.total_amount or 0),
                settled_count=row.total_transactions if row.status == TransactionStatus.SETTLED else 0,
                settled_amount=float(row.total_amount or 0) if row.status == TransactionStatus.SETTLED else 0.0,
                processed_count=row.total_transactions if row.status == TransactionStatus.PROCESSED else 0,
                processed_amount=float(row.total_amount or 0) if row.status == TransactionStatus.PROCESSED else 0.0,
                failed_count=row.total_transactions if row.status == TransactionStatus.FAILED else 0,
                failed_amount=float(row.total_amount or 0) if row.status == TransactionStatus.FAILED else 0.0,
                initiated_count=row.total_transactions if row.status == TransactionStatus.INITIATED else 0,
                initiated_amount=float(row.total_amount or 0) if row.status == TransactionStatus.INITIATED else 0.0,
                settlement_rate=100.0 if row.status == TransactionStatus.SETTLED else 0.0,
            )
            for row in rows
        ]

    def _get_totals(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Get aggregate totals."""
        
        query = select(
            func.count(Transaction.id).label("total_transactions"),
            func.sum(Transaction.amount).label("total_amount"),
            func.sum(case((Transaction.status == TransactionStatus.SETTLED, 1), else_=0)).label("settled_count"),
            func.sum(case((Transaction.status == TransactionStatus.SETTLED, Transaction.amount), else_=0)).label("settled_amount"),
        )
        
        query = self._apply_filters(query, merchant_id, start_date, end_date)
        row = self.db.execute(query).fetchone()
        
        total = row.total_transactions or 0
        settled = row.settled_count or 0
        
        return {
            "total_transactions": total,
            "total_amount": float(row.total_amount or 0),
            "settled_count": settled,
            "settled_amount": float(row.settled_amount or 0),
            "settlement_rate": round((settled / total * 100), 2) if total > 0 else 0.0,
        }
    
    def _apply_filters(self, query, merchant_id, start_date, end_date):
        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)
        return query
    
    # ========== Discrepancy Detection ==========
    
    def get_discrepancies(
        self,
        merchant_id: Optional[str] = None,
        discrepancy_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> DiscrepancyListResponse:
        """Find transactions with anomalies."""
        
        discrepancies = []
        summary = {
            "processed_not_settled": 0,
            "settled_after_failure": 0,
            "duplicate_settlement": 0,
            "missing_initiation": 0,
            "conflicting_events": 0,
        }
        
        # Get each type of discrepancy
        if not discrepancy_type or discrepancy_type == "processed_not_settled":
            items = self._find_processed_not_settled(merchant_id, start_date, end_date)
            summary["processed_not_settled"] = len(items)
            discrepancies.extend(items)
        
        if not discrepancy_type or discrepancy_type == "settled_after_failure":
            items = self._find_settled_after_failure(merchant_id, start_date, end_date)
            summary["settled_after_failure"] = len(items)
            discrepancies.extend(items)
        
        if not discrepancy_type or discrepancy_type == "duplicate_settlement":
            items = self._find_duplicate_settlement(merchant_id, start_date, end_date)
            summary["duplicate_settlement"] = len(items)
            discrepancies.extend(items)
        
        if not discrepancy_type or discrepancy_type == "missing_initiation":
            items = self._find_missing_initiation(merchant_id, start_date, end_date)
            summary["missing_initiation"] = len(items)
            discrepancies.extend(items)
        
        if not discrepancy_type or discrepancy_type == "conflicting_events":
            items = self._find_conflicting_events(merchant_id, start_date, end_date)
            summary["conflicting_events"] = len(items)
            discrepancies.extend(items)
        
        # Paginate
        total = len(discrepancies)
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size
        
        return DiscrepancyListResponse(
            discrepancies=discrepancies[start:end],
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
            summary=summary,
        )
    
    def _find_processed_not_settled(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[DiscrepancyItem]:
        """Find transactions stuck in PROCESSED state (never settled)."""
        
        # Transactions in PROCESSED status that have no settlement event
        settled_event_exists = (
            select(Event.id)
            .where(Event.transaction_id == Transaction.id)
            .where(Event.event_type == EventType.SETTLED)
            .exists()
        )
        
        query = (
            select(Transaction)
            .options(selectinload(Transaction.merchant), selectinload(Transaction.events))
            .where(Transaction.status == TransactionStatus.PROCESSED)
            .where(~settled_event_exists)
        )
        
        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)
        
        transactions = self.db.execute(query).scalars().all()
        
        return [
            self._to_discrepancy(t, "processed_not_settled", "Transaction processed but never settled")
            for t in transactions
        ]
    
    def _find_settled_after_failure(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[DiscrepancyItem]:
        """Find transactions that have both FAILED and SETTLED events."""
        
        # Has both failure and settlement events
        has_failed = (
            select(Event.id)
            .where(Event.transaction_id == Transaction.id)
            .where(Event.event_type == EventType.PAYMENT_FAILED)
            .exists()
        )
        has_settled = (
            select(Event.id)
            .where(Event.transaction_id == Transaction.id)
            .where(Event.event_type == EventType.SETTLED)
            .exists()
        )
        
        query = (
            select(Transaction)
            .options(selectinload(Transaction.merchant), selectinload(Transaction.events))
            .where(has_failed)
            .where(has_settled)
        )
        
        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)
        
        transactions = self.db.execute(query).scalars().all()
        
        return [
            self._to_discrepancy(t, "settled_after_failure", "Settlement recorded after payment failure")
            for t in transactions
        ]
    
    def _find_duplicate_settlement(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[DiscrepancyItem]:
        """Find transactions with more than one SETTLED event."""

        # Subquery: transaction IDs with multiple settled events
        settled_count_sq = (
            select(
                Event.transaction_id,
                func.count(Event.id).label("settled_count"),
            )
            .where(Event.event_type == EventType.SETTLED)
            .group_by(Event.transaction_id)
            .having(func.count(Event.id) > 1)
            .subquery()
        )

        query = (
            select(Transaction)
            .options(selectinload(Transaction.merchant), selectinload(Transaction.events))
            .join(settled_count_sq, Transaction.id == settled_count_sq.c.transaction_id)
        )

        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)

        transactions = self.db.execute(query).scalars().all()

        return [
            self._to_discrepancy(t, "duplicate_settlement", "Transaction has multiple settlement events")
            for t in transactions
        ]

    def _find_missing_initiation(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[DiscrepancyItem]:
        """Find transactions that have no payment_initiated event."""

        has_initiation = (
            select(Event.id)
            .where(Event.transaction_id == Transaction.id)
            .where(Event.event_type == EventType.PAYMENT_INITIATED)
            .exists()
        )

        query = (
            select(Transaction)
            .options(selectinload(Transaction.merchant), selectinload(Transaction.events))
            .where(~has_initiation)
        )

        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)

        transactions = self.db.execute(query).scalars().all()

        return [
            self._to_discrepancy(t, "missing_initiation", "Transaction has no payment_initiated event")
            for t in transactions
        ]

    def _find_conflicting_events(
        self, merchant_id: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[DiscrepancyItem]:
        """Find transactions that have both FAILED and SETTLED events (conflicting terminal states)."""

        has_failed = (
            select(Event.id)
            .where(Event.transaction_id == Transaction.id)
            .where(Event.event_type == EventType.PAYMENT_FAILED)
            .exists()
        )
        has_settled = (
            select(Event.id)
            .where(Event.transaction_id == Transaction.id)
            .where(Event.event_type == EventType.SETTLED)
            .exists()
        )

        query = (
            select(Transaction)
            .options(selectinload(Transaction.merchant), selectinload(Transaction.events))
            .where(has_failed)
            .where(has_settled)
        )

        if merchant_id:
            query = query.where(Transaction.merchant_id == merchant_id)
        if start_date:
            query = query.where(Transaction.created_at >= start_date)
        if end_date:
            query = query.where(Transaction.created_at <= end_date)

        transactions = self.db.execute(query).scalars().all()

        return [
            self._to_discrepancy(t, "conflicting_events", "Transaction has both failed and settled events — conflicting state")
            for t in transactions
        ]

    def _to_discrepancy(self, txn: Transaction, disc_type: str, description: str) -> DiscrepancyItem:
        sorted_events = sorted(txn.events, key=lambda e: e.timestamp)
        
        return DiscrepancyItem(
            transaction_id=txn.id,
            merchant_id=txn.merchant_id,
            merchant_name=txn.merchant.name if txn.merchant else "Unknown",
            amount=float(txn.amount),
            currency=txn.currency,
            current_status=txn.status.value,
            discrepancy_type=disc_type,
            discrepancy_description=description,
            created_at=txn.created_at,
            events=[
                EventSummary(event_id=e.id, event_type=e.event_type.value, timestamp=e.timestamp)
                for e in sorted_events
            ],
        )
