"""
SQLAlchemy ORM models for the payment reconciliation system.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Numeric,
    ForeignKey,
    Index,
    Enum as SQLEnum,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, validates
import enum

from app.core.database import Base


def utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class EventType(str, enum.Enum):
    """Payment lifecycle event types."""
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_PROCESSED = "payment_processed"
    PAYMENT_FAILED = "payment_failed"
    SETTLED = "settled"


class TransactionStatus(str, enum.Enum):
    """Transaction status derived from events."""
    INITIATED = "initiated"
    PROCESSED = "processed"
    FAILED = "failed"
    SETTLED = "settled"


class Merchant(Base):
    """
    Merchant entity - represents a partner/merchant in the system.
    
    Merchants are auto-created when events are ingested if they don't exist.
    """
    
    __tablename__ = "merchants"
    
    id = Column(String(50), primary_key=True, comment="Unique merchant identifier")
    name = Column(String(255), nullable=False, comment="Human-readable merchant name")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="merchant", lazy="dynamic")
    
    def __repr__(self) -> str:
        return f"<Merchant(id={self.id}, name={self.name})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {"id": self.id, "name": self.name}


class Transaction(Base):
    """
    Transaction entity - represents a payment transaction.
    
    Status is derived from the latest event and denormalized here
    for query efficiency.
    """
    
    __tablename__ = "transactions"
    
    id = Column(String(50), primary_key=True, comment="Transaction UUID")
    merchant_id = Column(
        String(50), 
        ForeignKey("merchants.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True,
        comment="Associated merchant"
    )
    amount = Column(
        Numeric(15, 2), 
        nullable=False,
        comment="Transaction amount (2 decimal places)"
    )
    currency = Column(String(3), nullable=False, default="INR", comment="ISO currency code")
    status = Column(
        SQLEnum(TransactionStatus, name="transactionstatus", values_callable=lambda x: [e.value for e in x]), 
        nullable=False, 
        default=TransactionStatus.INITIATED,
        comment="Current status derived from latest event"
    )
    created_at = Column(DateTime(timezone=True), nullable=False, comment="When transaction was initiated")
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    # Relationships
    merchant = relationship("Merchant", back_populates="transactions", lazy="joined")
    events = relationship(
        "Event", 
        back_populates="transaction", 
        order_by="Event.timestamp",
        lazy="select",  # Default lazy loading, use selectinload() for eager loading
        cascade="all, delete-orphan"
    )
    
    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_transactions_status", "status"),
        Index("ix_transactions_created_at", "created_at"),
        Index("ix_transactions_merchant_status", "merchant_id", "status"),
        Index("ix_transactions_merchant_created", "merchant_id", "created_at"),
        Index("ix_transactions_status_created", "status", "created_at"),
        CheckConstraint("amount > 0", name="ck_transactions_positive_amount"),
    )
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, status={self.status}, amount={self.amount})>"
    
    @property
    def is_terminal_state(self) -> bool:
        """Check if transaction is in a terminal state (settled or failed)."""
        return self.status in (TransactionStatus.SETTLED, TransactionStatus.FAILED)


class Event(Base):
    """
    Event entity - represents a payment lifecycle event.
    
    Events are immutable and form the audit trail for transactions.
    The event.id (event_id) is the primary key ensuring idempotent ingestion.
    """
    
    __tablename__ = "events"
    
    # Primary key ensures idempotency - duplicate event_id will be rejected
    id = Column(String(50), primary_key=True, comment="Event UUID - ensures idempotent ingestion")
    event_type = Column(
        SQLEnum(EventType, name="eventtype", values_callable=lambda x: [e.value for e in x]), 
        nullable=False,
        comment="Type of payment lifecycle event"
    )
    transaction_id = Column(
        String(50), 
        ForeignKey("transactions.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True,
        comment="Associated transaction"
    )
    merchant_id = Column(
        String(50), 
        ForeignKey("merchants.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True,
        comment="Associated merchant (denormalized)"
    )
    amount = Column(Numeric(15, 2), nullable=False, comment="Amount at time of event")
    currency = Column(String(3), nullable=False, default="INR", comment="Currency at time of event")
    timestamp = Column(DateTime(timezone=True), nullable=False, comment="When event occurred in source")
    created_at = Column(
        DateTime(timezone=True), 
        default=utc_now, 
        nullable=False,
        comment="When event was ingested"
    )
    raw_payload = Column(Text, nullable=True, comment="Original JSON for audit/debugging")
    
    # Relationships
    transaction = relationship("Transaction", back_populates="events")
    merchant = relationship("Merchant", lazy="joined")
    
    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_events_event_type", "event_type"),
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_transaction_timestamp", "transaction_id", "timestamp"),
        Index("ix_events_type_timestamp", "event_type", "timestamp"),
        CheckConstraint("amount > 0", name="ck_events_positive_amount"),
    )
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type={self.event_type}, transaction={self.transaction_id})>"
    
    def to_summary(self) -> dict:
        """Convert to summary dict for event history."""
        return {
            "event_id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
        }
