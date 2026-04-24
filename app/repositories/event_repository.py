"""
Event Repository - Data access layer for events.
"""

from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.entities import Event, EventType


class EventRepository:
    """Repository for Event data access."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, event_id: str) -> Optional[Event]:
        """Get event by ID."""
        return self.db.query(Event).filter(Event.id == event_id).first()
    
    def exists(self, event_id: str) -> bool:
        """Check if event exists (for idempotency)."""
        return self.db.query(
            self.db.query(Event).filter(Event.id == event_id).exists()
        ).scalar()
    
    def create(self, event: Event) -> Tuple[Event, bool]:
        """
        Create a new event. Returns (event, is_new).
        If event already exists, returns existing event with is_new=False.
        """
        try:
            self.db.add(event)
            self.db.flush()
            return event, True
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_id(event.id)
            return existing, False
    
    def get_by_transaction_id(
        self,
        transaction_id: str,
        order_by_timestamp: bool = True,
    ) -> List[Event]:
        """Get all events for a transaction, ordered by timestamp."""
        query = self.db.query(Event).filter(Event.transaction_id == transaction_id)
        if order_by_timestamp:
            query = query.order_by(Event.timestamp)
        return query.all()
    
    def get_latest_by_transaction(self, transaction_id: str) -> Optional[Event]:
        """Get the most recent event for a transaction."""
        return (
            self.db.query(Event)
            .filter(Event.transaction_id == transaction_id)
            .order_by(Event.timestamp.desc())
            .first()
        )
    
    def count_by_type_for_transaction(
        self,
        transaction_id: str,
        event_type: EventType,
    ) -> int:
        """Count events of a specific type for a transaction."""
        return (
            self.db.query(Event)
            .filter(
                Event.transaction_id == transaction_id,
                Event.event_type == event_type,
            )
            .count()
        )
    
    def bulk_check_exists(self, event_ids: List[str]) -> set:
        """Check which event IDs already exist. Returns set of existing IDs."""
        if not event_ids:
            return set()
        
        result = (
            self.db.query(Event.id)
            .filter(Event.id.in_(event_ids))
            .all()
        )
        return {row[0] for row in result}
