"""
Pydantic Schemas for request/response validation.

This module exports all schemas for use across the application.
"""

from app.schemas.common import PaginationMeta, PaginatedResponse, ErrorResponse, SuccessResponse
from app.schemas.event import (
    EventTypeEnum,
    EventCreate,
    EventBulkCreate,
    EventResponse,
    EventSummary,
    BulkIngestResponse,
)
from app.schemas.transaction import (
    TransactionStatusEnum,
    MerchantInfo,
    TransactionResponse,
    TransactionDetailResponse,
    TransactionListResponse,
)
from app.schemas.reconciliation import (
    DiscrepancyType,
    SummaryItem,
    ReconciliationSummaryResponse,
    DiscrepancyItem,
    DiscrepancyListResponse,
)

__all__ = [
    # Common
    "PaginationMeta",
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
    # Event
    "EventTypeEnum",
    "EventCreate",
    "EventBulkCreate",
    "EventResponse",
    "EventSummary",
    "BulkIngestResponse",
    # Transaction
    "TransactionStatusEnum",
    "MerchantInfo",
    "TransactionResponse",
    "TransactionDetailResponse",
    "TransactionListResponse",
    # Reconciliation
    "DiscrepancyType",
    "SummaryItem",
    "ReconciliationSummaryResponse",
    "DiscrepancyItem",
    "DiscrepancyListResponse",
]
