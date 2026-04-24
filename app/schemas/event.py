"""Event-related Pydantic schemas."""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum
from decimal import Decimal


class EventTypeEnum(str, Enum):
    """Valid event types for payment lifecycle."""
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_PROCESSED = "payment_processed"
    PAYMENT_FAILED = "payment_failed"
    SETTLED = "settled"


class EventCreate(BaseModel):
    """
    Schema for creating/ingesting a payment event.
    """
    
    event_id: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Unique identifier for this event (used for idempotency)"
    )
    event_type: EventTypeEnum = Field(..., description="Type of payment event")
    transaction_id: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Associated transaction ID"
    )
    merchant_id: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Merchant identifier"
    )
    merchant_name: str = Field(
        ..., 
        min_length=1,
        max_length=255,
        description="Merchant display name"
    )
    amount: float = Field(..., gt=0, description="Transaction amount (must be positive)")
    currency: str = Field(default="INR", max_length=3, description="ISO 4217 currency code")
    timestamp: datetime = Field(..., description="When the event occurred (ISO 8601)")
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Normalize currency to uppercase."""
        return v.upper().strip()
    
    @field_validator("event_id", "transaction_id", "merchant_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        """Strip whitespace from IDs."""
        return v.strip()
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "event_id": "b768e3a7-9eb3-4603-b21c-a54cc95661bc",
                "event_type": "payment_initiated",
                "transaction_id": "2f86e94c-239c-4302-9874-75f28e3474ee",
                "merchant_id": "merchant_2",
                "merchant_name": "FreshBasket",
                "amount": 15248.29,
                "currency": "INR",
                "timestamp": "2026-01-08T12:11:58.085567+00:00"
            }
        }
    )


class EventBulkCreate(BaseModel):
    """Schema for bulk event ingestion."""
    
    events: List[EventCreate] = Field(
        ..., 
        min_length=1,
        max_length=50000,
        description="List of events to ingest (optimized for 10K+ per request)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events": [
                    {
                        "event_id": "evt-001",
                        "event_type": "payment_initiated",
                        "transaction_id": "txn-001",
                        "merchant_id": "merchant_1",
                        "merchant_name": "TechGadgets",
                        "amount": 1000.00,
                        "currency": "INR",
                        "timestamp": "2026-01-15T10:00:00Z"
                    }
                ]
            }
        }
    )


class EventResponse(BaseModel):
    """Schema for event response after ingestion."""
    
    event_id: str
    event_type: str
    transaction_id: str
    merchant_id: str
    amount: float
    currency: str
    timestamp: datetime
    created_at: datetime
    is_duplicate: bool = Field(
        default=False, 
        description="True if this event was already ingested (idempotency)"
    )
    
    model_config = ConfigDict(from_attributes=True)


class EventSummary(BaseModel):
    """Simplified event for transaction event history."""
    
    event_id: str
    event_type: str
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BulkIngestResponse(BaseModel):
    """Response schema for bulk event ingestion."""
    
    total_received: int = Field(..., description="Total events in request")
    successful: int = Field(..., description="Events successfully ingested")
    duplicates: int = Field(..., description="Duplicate events skipped (idempotent)")
    failed: int = Field(..., description="Events that failed validation")
    errors: List[str] = Field(default=[], description="Error details for failed events")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_received": 100,
                "successful": 95,
                "duplicates": 4,
                "failed": 1,
                "errors": ["Batch failed: duplicate key"]
            }
        }
    )
