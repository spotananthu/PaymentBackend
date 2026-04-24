"""Transaction-related Pydantic schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.schemas.common import PaginationMeta
from app.schemas.event import EventSummary


class TransactionStatusEnum(str, Enum):
    """Transaction status values."""
    INITIATED = "initiated"
    PROCESSED = "processed"
    FAILED = "failed"
    SETTLED = "settled"


class MerchantInfo(BaseModel):
    """Merchant information embedded in transaction responses."""
    
    id: str = Field(..., description="Merchant identifier")
    name: str = Field(..., description="Merchant display name")
    
    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    """
    Schema for transaction in list responses.
    
    Used in GET /transactions endpoint for paginated list.
    """
    
    transaction_id: str = Field(..., alias="id", description="Unique transaction identifier")
    merchant_id: str = Field(..., description="Associated merchant ID")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="ISO 4217 currency code")
    status: str = Field(..., description="Current transaction status")
    created_at: datetime = Field(..., description="When transaction was initiated")
    updated_at: datetime = Field(..., description="Last status update time")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "transaction_id": "2f86e94c-239c-4302-9874-75f28e3474ee",
                "merchant_id": "merchant_2",
                "amount": 15248.29,
                "currency": "INR",
                "status": "settled",
                "created_at": "2026-01-08T12:11:58.085567+00:00",
                "updated_at": "2026-01-08T14:30:00.000000+00:00"
            }
        }
    )


class TransactionDetailResponse(BaseModel):
    """
    Schema for detailed transaction response with event history.
    
    Used in GET /transactions/{transaction_id} endpoint.
    Includes full merchant info and complete event history.
    """
    
    transaction_id: str = Field(..., description="Unique transaction identifier")
    merchant: MerchantInfo = Field(..., description="Merchant information")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="ISO 4217 currency code")
    status: str = Field(..., description="Current transaction status")
    created_at: datetime = Field(..., description="When transaction was initiated")
    updated_at: datetime = Field(..., description="Last status update time")
    event_count: int = Field(..., description="Total number of events")
    events: List[EventSummary] = Field(
        ..., 
        description="Event history ordered by timestamp"
    )
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "transaction_id": "2f86e94c-239c-4302-9874-75f28e3474ee",
                "merchant": {"id": "merchant_2", "name": "FreshBasket"},
                "amount": 15248.29,
                "currency": "INR",
                "status": "settled",
                "created_at": "2026-01-08T12:11:58.085567+00:00",
                "updated_at": "2026-01-08T14:30:00.000000+00:00",
                "event_count": 3,
                "events": [
                    {"event_id": "evt-001", "event_type": "payment_initiated", "timestamp": "2026-01-08T12:11:58Z"},
                    {"event_id": "evt-002", "event_type": "payment_processed", "timestamp": "2026-01-08T12:15:00Z"},
                    {"event_id": "evt-003", "event_type": "settled", "timestamp": "2026-01-08T14:30:00Z"}
                ]
            }
        }
    )


class TransactionListResponse(BaseModel):
    """Paginated transaction list response."""
    
    transactions: List[TransactionResponse] = Field(..., description="List of transactions")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
