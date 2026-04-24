"""
Script to load sample events into the database.
"""

import json
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine, Base
from app.models.entities import Event, Transaction, Merchant
from app.services.event_service import EventService
from app.schemas.event import EventCreate


def load_events_from_file(filepath: str):
    """Load events from JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp string to datetime."""
    # Handle various timestamp formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    
    # Fallback - remove timezone info and try again
    if "+" in ts_str:
        ts_str = ts_str.split("+")[0]
    
    return datetime.fromisoformat(ts_str.replace("Z", ""))


def main():
    parser = argparse.ArgumentParser(description="Load sample events into database")
    parser.add_argument(
        "--file",
        type=str,
        default="sample_events.json",
        help="Path to events JSON file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of events to process per batch",
    )
    args = parser.parse_args()
    
    # Create tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Load events
    print(f"Loading events from {args.file}...")
    events_data = load_events_from_file(args.file)
    print(f"Loaded {len(events_data)} events")
    
    # Process events
    db = SessionLocal()
    service = EventService(db)
    
    successful = 0
    duplicates = 0
    failed = 0
    
    print("Processing events...")
    for i, event_data in enumerate(events_data):
        try:
            event = EventCreate(
                event_id=event_data["event_id"],
                event_type=event_data["event_type"],
                transaction_id=event_data["transaction_id"],
                merchant_id=event_data["merchant_id"],
                merchant_name=event_data["merchant_name"],
                amount=event_data["amount"],
                currency=event_data.get("currency", "INR"),
                timestamp=parse_timestamp(event_data["timestamp"]),
            )
            
            result = service.ingest_event(event)
            
            if result.is_duplicate:
                duplicates += 1
            else:
                successful += 1
                
        except Exception as e:
            failed += 1
            print(f"Error processing event {event_data.get('event_id')}: {e}")
        
        # Progress update
        if (i + 1) % args.batch_size == 0:
            print(f"Processed {i + 1}/{len(events_data)} events...")
    
    db.close()
    
    print("\nLoading complete!")
    print(f"  Successful: {successful}")
    print(f"  Duplicates: {duplicates}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
