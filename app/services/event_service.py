"""
Event Service - Event ingestion with idempotency and state machine.
"""

from typing import List, Tuple
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.models.entities import Event, Transaction, Merchant, EventType, TransactionStatus
from app.schemas.event import EventCreate, EventResponse, BulkIngestResponse
from app.core.state_machine import compute_transition

logger = logging.getLogger(__name__)


class EventService:
    """Handles idempotent event ingestion and transaction state management."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def ingest_event(self, event_data: EventCreate) -> EventResponse:
        """
        Ingest a single payment event (idempotent).
        
        Flow: Check duplicate -> Ensure merchant -> Get/create transaction -> Create event -> Update status
        """
        # Idempotency check
        existing = self.db.get(Event, event_data.event_id)
        if existing:
            return self._to_response(existing, is_duplicate=True)
        
        try:
            self._get_or_create_merchant(event_data.merchant_id, event_data.merchant_name)
            transaction = self._get_or_create_transaction(event_data)
            
            event = Event(
                id=event_data.event_id,
                event_type=EventType(event_data.event_type.value),
                transaction_id=event_data.transaction_id,
                merchant_id=event_data.merchant_id,
                amount=event_data.amount,
                currency=event_data.currency,
                timestamp=event_data.timestamp,
            )
            self.db.add(event)
            self._update_transaction_status(transaction, event.event_type, event_data.timestamp)
            self.db.commit()
            
            return self._to_response(event, is_duplicate=False)
            
        except IntegrityError:
            self.db.rollback()
            existing = self.db.get(Event, event_data.event_id)
            if existing:
                return self._to_response(existing, is_duplicate=True)
            raise
    
    def ingest_events_bulk(self, events: List[EventCreate]) -> BulkIngestResponse:
        """
        Optimized bulk ingestion for 10,000+ events.
        
        Strategy: Pre-fetch duplicates -> Batch in 500s -> Group by transaction
        """
        if not events:
            return BulkIngestResponse(total_received=0, successful=0, duplicates=0, failed=0, errors=[])
        
        # De-duplicate within the input list (keep first occurrence)
        seen_ids: dict[str, EventCreate] = {}
        input_duplicates = 0
        for e in events:
            if e.event_id in seen_ids:
                input_duplicates += 1
            else:
                seen_ids[e.event_id] = e
        unique_events = list(seen_ids.values())
        
        # Pre-fetch existing event IDs from DB
        event_ids = [e.event_id for e in unique_events]
        existing_ids = set(
            row[0] for row in self.db.execute(
                select(Event.id).where(Event.id.in_(event_ids))
            ).fetchall()
        )
        
        duplicates = len(existing_ids) + input_duplicates
        new_events = sorted(
            [e for e in unique_events if e.event_id not in existing_ids],
            key=lambda e: e.timestamp
        )
        
        successful, failed, errors = 0, 0, []
        
        # Process in batches of 500
        for i in range(0, len(new_events), 500):
            batch = new_events[i:i + 500]
            s, f, e = self._process_batch(batch)
            successful += s
            failed += f
            errors.extend(e)
        
        return BulkIngestResponse(
            total_received=len(events),
            successful=successful,
            duplicates=duplicates,
            failed=failed,
            errors=errors[:100],
        )
    
    def _process_batch(self, events: List[EventCreate]) -> Tuple[int, int, List[str]]:
        """Process a batch of events atomically."""
        successful, failed, errors = 0, 0, []
        
        # Group by transaction
        by_txn = {}
        for e in events:
            by_txn.setdefault(e.transaction_id, []).append(e)
        
        try:
            # Ensure all merchants exist
            for merchant_id, merchant_name in {(e.merchant_id, e.merchant_name) for e in events}:
                self._get_or_create_merchant(merchant_id, merchant_name)
            
            # Process each transaction's events in order
            for txn_id, txn_events in by_txn.items():
                txn_events.sort(key=lambda e: e.timestamp)
                transaction = self._get_or_create_transaction(txn_events[0])
                
                for event_data in txn_events:
                    event = Event(
                        id=event_data.event_id,
                        event_type=EventType(event_data.event_type.value),
                        transaction_id=event_data.transaction_id,
                        merchant_id=event_data.merchant_id,
                        amount=event_data.amount,
                        currency=event_data.currency,
                        timestamp=event_data.timestamp,
                    )
                    self.db.add(event)
                    self._update_transaction_status(transaction, event.event_type, event_data.timestamp)
                    successful += 1
            
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            failed = len(events)
            errors.append(f"Batch failed: {str(e)}")
        
        return successful, failed, errors
    
    def _get_or_create_merchant(self, merchant_id: str, merchant_name: str) -> Merchant:
        merchant = self.db.get(Merchant, merchant_id)
        if not merchant:
            merchant = Merchant(id=merchant_id, name=merchant_name)
            self.db.add(merchant)
            self.db.flush()
        return merchant
    
    def _get_or_create_transaction(self, event_data: EventCreate) -> Transaction:
        transaction = self.db.get(Transaction, event_data.transaction_id)
        if not transaction:
            transaction = Transaction(
                id=event_data.transaction_id,
                merchant_id=event_data.merchant_id,
                amount=event_data.amount,
                currency=event_data.currency,
                status=TransactionStatus.INITIATED,
                created_at=event_data.timestamp,
            )
            self.db.add(transaction)
            self.db.flush()
        return transaction
    
    def _update_transaction_status(self, transaction: Transaction, event_type: EventType, timestamp: datetime):
        result = compute_transition(transaction.status, event_type)
        if result.allowed and result.new_status is not None and result.new_status != transaction.status:
            transaction.status = result.new_status
            transaction.updated_at = timestamp
    
    def _to_response(self, event: Event, is_duplicate: bool) -> EventResponse:
        return EventResponse(
            event_id=event.id,
            event_type=event.event_type.value,
            transaction_id=event.transaction_id,
            merchant_id=event.merchant_id,
            amount=float(event.amount),
            currency=event.currency,
            timestamp=event.timestamp,
            created_at=event.created_at,
            is_duplicate=is_duplicate,
        )
