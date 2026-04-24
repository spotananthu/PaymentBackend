"""
Sample data generator for testing the payment reconciliation service.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict
import argparse


# Merchant data
MERCHANTS = [
    {"id": "merchant_1", "name": "TechGadgets"},
    {"id": "merchant_2", "name": "FreshBasket"},
    {"id": "merchant_3", "name": "StyleHub"},
    {"id": "merchant_4", "name": "HomeDecor"},
    {"id": "merchant_5", "name": "BookWorld"},
]

# Event types in lifecycle order
EVENT_TYPES = [
    "payment_initiated",
    "payment_processed",
    "settled",
]


def generate_timestamp(base_time: datetime, offset_minutes: int = 0) -> str:
    """Generate ISO format timestamp."""
    ts = base_time + timedelta(minutes=offset_minutes)
    return ts.isoformat()


def generate_amount() -> float:
    """Generate random transaction amount."""
    return round(random.uniform(100, 50000), 2)


def generate_normal_flow(
    transaction_id: str,
    merchant: Dict,
    start_time: datetime,
) -> List[Dict]:
    """Generate events for a successful transaction flow."""
    amount = generate_amount()
    events = []
    
    # Payment initiated
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_initiated",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time),
    })
    
    # Payment processed (1-5 minutes later)
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_processed",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(1, 5)),
    })
    
    # Settled (1-24 hours later)
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "settled",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(60, 1440)),
    })
    
    return events


def generate_failed_flow(
    transaction_id: str,
    merchant: Dict,
    start_time: datetime,
) -> List[Dict]:
    """Generate events for a failed transaction."""
    amount = generate_amount()
    events = []
    
    # Payment initiated
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_initiated",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time),
    })
    
    # Payment failed
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_failed",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(1, 5)),
    })
    
    return events


def generate_processed_not_settled(
    transaction_id: str,
    merchant: Dict,
    start_time: datetime,
) -> List[Dict]:
    """Generate events for a transaction stuck in processed state (discrepancy)."""
    amount = generate_amount()
    events = []
    
    # Payment initiated
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_initiated",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time),
    })
    
    # Payment processed but never settled
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_processed",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(1, 5)),
    })
    
    return events


def generate_settled_after_failure(
    transaction_id: str,
    merchant: Dict,
    start_time: datetime,
) -> List[Dict]:
    """Generate events for settlement after failure (discrepancy)."""
    amount = generate_amount()
    events = []
    
    # Payment initiated
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_initiated",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time),
    })
    
    # Payment failed
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_failed",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(1, 5)),
    })
    
    # Settled anyway (incorrect - discrepancy)
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "settled",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(60, 1440)),
    })
    
    return events


def generate_duplicate_settlement(
    transaction_id: str,
    merchant: Dict,
    start_time: datetime,
) -> List[Dict]:
    """Generate events with duplicate settlements (discrepancy)."""
    amount = generate_amount()
    events = []
    
    # Payment initiated
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_initiated",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time),
    })
    
    # Payment processed
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_processed",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(1, 5)),
    })
    
    # First settlement
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "settled",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(60, 1440)),
    })
    
    # Duplicate settlement
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "settled",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(1500, 2880)),
    })
    
    return events


def generate_missing_initiation(
    transaction_id: str,
    merchant: Dict,
    start_time: datetime,
) -> List[Dict]:
    """Generate events without initiation event (discrepancy)."""
    amount = generate_amount()
    events = []
    
    # Directly processed (missing initiation)
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "payment_processed",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time),
    })
    
    # Settled
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": "settled",
        "transaction_id": transaction_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": amount,
        "currency": "INR",
        "timestamp": generate_timestamp(start_time, random.randint(60, 1440)),
    })
    
    return events


def add_duplicate_events(events: List[Dict], duplicate_rate: float = 0.05) -> List[Dict]:
    """Add duplicate events to simulate real-world scenarios."""
    duplicates = []
    for event in events:
        if random.random() < duplicate_rate:
            duplicates.append(event.copy())
    return events + duplicates


def generate_sample_events(
    total_transactions: int = 3000,
    start_date: datetime = None,
) -> List[Dict]:
    """
    Generate sample events with realistic distribution of scenarios.
    """
    if start_date is None:
        start_date = datetime(2026, 1, 1, 0, 0, 0)
    
    all_events = []
    
    # Calculate counts for each scenario
    successful_count = int(total_transactions * 0.70)
    failed_count = int(total_transactions * 0.15)
    processed_not_settled_count = int(total_transactions * 0.05)
    settled_after_failure_count = int(total_transactions * 0.03)
    duplicate_settlement_count = int(total_transactions * 0.04)
    missing_initiation_count = total_transactions - (
        successful_count + failed_count + processed_not_settled_count +
        settled_after_failure_count + duplicate_settlement_count
    )
    
    print(f"Generating events for {total_transactions} transactions:")
    print(f"  - Successful: {successful_count}")
    print(f"  - Failed: {failed_count}")
    print(f"  - Processed not settled: {processed_not_settled_count}")
    print(f"  - Settled after failure: {settled_after_failure_count}")
    print(f"  - Duplicate settlement: {duplicate_settlement_count}")
    print(f"  - Missing initiation: {missing_initiation_count}")
    
    # Generate events for each scenario
    time_offset = 0
    
    for i in range(successful_count):
        transaction_id = str(uuid.uuid4())
        merchant = random.choice(MERCHANTS)
        transaction_time = start_date + timedelta(minutes=time_offset)
        events = generate_normal_flow(transaction_id, merchant, transaction_time)
        all_events.extend(events)
        time_offset += random.randint(1, 30)
    
    for i in range(failed_count):
        transaction_id = str(uuid.uuid4())
        merchant = random.choice(MERCHANTS)
        transaction_time = start_date + timedelta(minutes=time_offset)
        events = generate_failed_flow(transaction_id, merchant, transaction_time)
        all_events.extend(events)
        time_offset += random.randint(1, 30)
    
    for i in range(processed_not_settled_count):
        transaction_id = str(uuid.uuid4())
        merchant = random.choice(MERCHANTS)
        transaction_time = start_date + timedelta(minutes=time_offset)
        events = generate_processed_not_settled(transaction_id, merchant, transaction_time)
        all_events.extend(events)
        time_offset += random.randint(1, 30)
    
    for i in range(settled_after_failure_count):
        transaction_id = str(uuid.uuid4())
        merchant = random.choice(MERCHANTS)
        transaction_time = start_date + timedelta(minutes=time_offset)
        events = generate_settled_after_failure(transaction_id, merchant, transaction_time)
        all_events.extend(events)
        time_offset += random.randint(1, 30)
    
    for i in range(duplicate_settlement_count):
        transaction_id = str(uuid.uuid4())
        merchant = random.choice(MERCHANTS)
        transaction_time = start_date + timedelta(minutes=time_offset)
        events = generate_duplicate_settlement(transaction_id, merchant, transaction_time)
        all_events.extend(events)
        time_offset += random.randint(1, 30)
    
    for i in range(missing_initiation_count):
        transaction_id = str(uuid.uuid4())
        merchant = random.choice(MERCHANTS)
        transaction_time = start_date + timedelta(minutes=time_offset)
        events = generate_missing_initiation(transaction_id, merchant, transaction_time)
        all_events.extend(events)
        time_offset += random.randint(1, 30)
    
    # Add some duplicate events (about 5%)
    all_events = add_duplicate_events(all_events, duplicate_rate=0.05)
    
    # Shuffle to simulate real-world event arrival
    random.shuffle(all_events)
    
    print(f"\nTotal events generated: {len(all_events)}")
    
    return all_events


def main():
    parser = argparse.ArgumentParser(description="Generate sample payment events")
    parser.add_argument(
        "--transactions",
        type=int,
        default=3000,
        help="Number of transactions to generate (default: 3000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="sample_events.json",
        help="Output file path (default: sample_events.json)",
    )
    args = parser.parse_args()
    
    events = generate_sample_events(total_transactions=args.transactions)
    
    with open(args.output, "w") as f:
        json.dump(events, f, indent=2, default=str)
    
    print(f"\nEvents written to {args.output}")


if __name__ == "__main__":
    main()
