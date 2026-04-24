"""Reconciliation-related Pydantic schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

from app.schemas.common import PaginationMeta
from app.schemas.event import EventSummary


class DiscrepancyType(str, Enum):
    """Types of reconciliation discrepancies."""
    PROCESSED_NOT_SETTLED = "processed_not_settled"
    SETTLED_AFTER_FAILURE = "settled_after_failure"
    DUPLICATE_SETTLEMENT = "duplicate_settlement"
    MISSING_INITIATION = "missing_initiation"
    INVALID_STATE_TRANSITION = "invalid_state_transition"


class SummaryItem(BaseModel):
    """A single summary row in reconciliation report."""
    
    group_key: str = Field(..., description="The grouping dimension value")
    group_value: Optional[str] = Field(None, description="Secondary group value if applicable")
    total_transactions: int
    total_amount: float
    settled_count: int
    settled_amount: float
    processed_count: int
    processed_amount: float
    failed_count: int
    failed_amount: float
    initiated_count: int
    initiated_amount: float
    settlement_rate: float = Field(..., description="Percentage of transactions that settled")


class ReconciliationSummaryResponse(BaseModel):
    """Response schema for reconciliation summary."""
    
    group_by: str = Field(..., description="Dimension used for grouping")
    period: Optional[Dict[str, str]] = Field(None, description="Date range if applicable")
    summary: List[SummaryItem]
    totals: Dict[str, Any] = Field(..., description="Aggregate totals across all groups")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DiscrepancyItem(BaseModel):
    """A single discrepancy record."""
    
    transaction_id: str
    merchant_id: str
    merchant_name: str
    amount: float
    currency: str
    current_status: str
    discrepancy_type: str
    discrepancy_description: str
    created_at: datetime
    events: List[EventSummary] = Field(..., description="Event history showing the inconsistency")


class DiscrepancyListResponse(BaseModel):
    """Paginated discrepancy list response."""
    
    discrepancies: List[DiscrepancyItem]
    pagination: PaginationMeta
    summary: Dict[str, int] = Field(..., description="Count by discrepancy type")
