"""
Transaction State Machine - Manages payment transaction state transitions.
"""

from enum import Enum
from typing import Optional, Tuple, List
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class TransactionStatus(str, Enum):
    """Transaction lifecycle states."""
    INITIATED = "initiated"
    PROCESSED = "processed"
    FAILED = "failed"
    SETTLED = "settled"


class EventType(str, Enum):
    """Payment event types that trigger state changes."""
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_PROCESSED = "payment_processed"
    PAYMENT_FAILED = "payment_failed"
    SETTLED = "settled"


@dataclass(frozen=True)
class TransitionResult:
    """Result of a state transition attempt."""
    allowed: bool
    new_status: Optional[TransactionStatus]
    reason: str
    
    @property
    def should_update(self) -> bool:
        """True if the transition should be applied to the database."""
        return self.allowed and self.new_status is not None


# Event type to status mapping
EVENT_TO_STATUS: dict[EventType, TransactionStatus] = {
    EventType.PAYMENT_INITIATED: TransactionStatus.INITIATED,
    EventType.PAYMENT_PROCESSED: TransactionStatus.PROCESSED,
    EventType.PAYMENT_FAILED: TransactionStatus.FAILED,
    EventType.SETTLED: TransactionStatus.SETTLED,
}

# Status precedence for out-of-order handling
STATUS_PRECEDENCE: dict[TransactionStatus, int] = {
    TransactionStatus.INITIATED: 1,
    TransactionStatus.PROCESSED: 2,
    TransactionStatus.SETTLED: 3,   # Terminal - highest for success path
    TransactionStatus.FAILED: 3,    # Terminal - same level as settled
}

# Valid state transitions (current_status -> set of allowed_new_statuses)
VALID_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.INITIATED: {
        TransactionStatus.PROCESSED,  # Normal progression
        TransactionStatus.FAILED,     # Payment can fail at initiation
    },
    TransactionStatus.PROCESSED: {
        TransactionStatus.SETTLED,    # Normal completion
        TransactionStatus.FAILED,     # Payment can fail after processing
    },
    TransactionStatus.FAILED: set(),   # Terminal state - no transitions allowed
    TransactionStatus.SETTLED: set(),  # Terminal state - no transitions allowed
}

# Terminal states that cannot transition to any other state
TERMINAL_STATES: set[TransactionStatus] = {
    TransactionStatus.FAILED,
    TransactionStatus.SETTLED,
}


def get_status_for_event(event_type: EventType) -> Optional[TransactionStatus]:
    """
    Map an event type to its corresponding transaction status.
    
    Args:
        event_type: The type of payment event
        
    Returns:
        The corresponding TransactionStatus, or None if unknown event type
        
    Example:
        >>> get_status_for_event(EventType.PAYMENT_PROCESSED)
        TransactionStatus.PROCESSED
    """
    return EVENT_TO_STATUS.get(event_type)


def is_terminal_state(status: TransactionStatus) -> bool:
    """
    Check if a status is a terminal (final) state.
    """
    return status in TERMINAL_STATES


def is_valid_transition(
    current_status: TransactionStatus,
    new_status: TransactionStatus,
) -> bool:
    """
    Check if a state transition is allowed.
    """
    if current_status == new_status:
        return False  # No-op transitions are not "valid" (nothing to do)
    
    allowed_transitions = VALID_TRANSITIONS.get(current_status, set())
    return new_status in allowed_transitions


def compute_transition(
    current_status: TransactionStatus,
    event_type: EventType,
    event_timestamp: Optional[datetime] = None,
    current_updated_at: Optional[datetime] = None,
) -> TransitionResult:
    """
    Compute the result of applying an event to a transaction.
    """
    # Step 1: Map event to target status
    target_status = get_status_for_event(event_type)
    
    if target_status is None:
        return TransitionResult(
            allowed=False,
            new_status=None,
            reason=f"Unknown event type: {event_type}",
        )
    
    # Step 2: Check if same status (no-op)
    if current_status == target_status:
        return TransitionResult(
            allowed=True,  # It's okay, just nothing to do
            new_status=None,
            reason="Event would result in same status (no-op)",
        )
    
    # Step 3: Check if current state is terminal
    if is_terminal_state(current_status):
        return TransitionResult(
            allowed=False,
            new_status=None,
            reason=f"Cannot transition from terminal state '{current_status.value}'",
        )
    
    # Step 4: Check if transition is valid
    if is_valid_transition(current_status, target_status):
        return TransitionResult(
            allowed=True,
            new_status=target_status,
            reason=f"Valid transition: {current_status.value} -> {target_status.value}",
        )
    
    # Step 5: Handle out-of-order events
    # If the event has a timestamp earlier than current state, it's out-of-order
    if event_timestamp and current_updated_at:
        if event_timestamp < current_updated_at:
            return TransitionResult(
                allowed=False,
                new_status=None,
                reason=f"Out-of-order event: event timestamp {event_timestamp} is before "
                       f"last update {current_updated_at}",
            )
    
    # Step 6: Invalid transition
    return TransitionResult(
        allowed=False,
        new_status=None,
        reason=f"Invalid transition: {current_status.value} -> {target_status.value}",
    )


def update_transaction_status(
    transaction,  # Transaction ORM object
    event_type: EventType,
    event_timestamp: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    Update a transaction's status based on an incoming event.
    """
    from datetime import timezone
    
    # Convert string status to enum if needed
    current_status = (
        TransactionStatus(transaction.status) 
        if isinstance(transaction.status, str) 
        else transaction.status
    )
    
    # Convert string event type to enum if needed  
    if isinstance(event_type, str):
        event_type = EventType(event_type)
    
    # Compute the transition
    result = compute_transition(
        current_status=current_status,
        event_type=event_type,
        event_timestamp=event_timestamp,
        current_updated_at=getattr(transaction, 'updated_at', None),
    )
    
    # Log the decision
    if result.should_update:
        logger.info(
            f"Transaction {transaction.id}: {current_status.value} -> "
            f"{result.new_status.value} ({result.reason})"
        )
    else:
        logger.debug(
            f"Transaction {transaction.id}: No status update - {result.reason}"
        )
    
    # Apply the update if valid
    if result.should_update:
        transaction.status = result.new_status
        transaction.updated_at = datetime.now(timezone.utc)
        return True, result.reason
    
    return False, result.reason


def get_valid_next_states(current_status: TransactionStatus) -> List[TransactionStatus]:
    """
    Get all valid states that can be transitioned to from the current state.
    """
    return list(VALID_TRANSITIONS.get(current_status, set()))


def validate_event_sequence(events: List[Tuple[EventType, datetime]]) -> List[str]:
    """
    Validate a sequence of events for a transaction.
    """
    if not events:
        return ["No events provided"]
    
    errors = []
    current_status = TransactionStatus.INITIATED
    
    # Sort by timestamp to ensure correct order
    sorted_events = sorted(events, key=lambda x: x[1])
    
    # Check first event
    first_event = sorted_events[0][0]
    if first_event != EventType.PAYMENT_INITIATED:
        errors.append(
            f"Transaction should start with payment_initiated, "
            f"but started with {first_event.value}"
        )
    else:
        current_status = TransactionStatus.INITIATED
    
    # Validate each transition
    for event_type, timestamp in sorted_events[1:]:
        target_status = get_status_for_event(event_type)
        
        if target_status is None:
            errors.append(f"Unknown event type: {event_type}")
            continue
        
        if not is_valid_transition(current_status, target_status):
            errors.append(
                f"Invalid transition: {current_status.value} -> {target_status.value} "
                f"(from event {event_type.value} at {timestamp})"
            )
        
        # Update current status for next iteration
        current_status = target_status
    
    return errors