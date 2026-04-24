"""
Tests for the Events API endpoints.
"""

import pytest
from fastapi import status


class TestEventIngestion:
    """Test cases for event ingestion."""
    
    def test_ingest_single_event(self, client, sample_event):
        """Test successful single event ingestion."""
        response = client.post("/events", json=sample_event)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["event_id"] == sample_event["event_id"]
        assert data["is_duplicate"] == False
    
    def test_idempotency_duplicate_event(self, client, sample_event):
        """Test that duplicate events are handled idempotently."""
        # First submission
        response1 = client.post("/events", json=sample_event)
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.json()["is_duplicate"] == False
        
        # Duplicate submission
        response2 = client.post("/events", json=sample_event)
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.json()["is_duplicate"] == True
    
    def test_bulk_event_ingestion(self, client, sample_events_flow):
        """Test bulk event ingestion."""
        response = client.post("/events/bulk", json={"events": sample_events_flow})
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_received"] == 3
        assert data["successful"] == 3
        assert data["duplicates"] == 0
        assert data["failed"] == 0
    
    def test_bulk_with_duplicates(self, client, sample_events_flow):
        """Test bulk ingestion handles duplicates."""
        # First submission
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        # Second submission with same events
        response = client.post("/events/bulk", json={"events": sample_events_flow})
        
        data = response.json()
        assert data["duplicates"] == 3
        assert data["successful"] == 0
    
    def test_bulk_large_batch(self, client):
        """Test bulk ingestion with larger batch (100 events)."""
        events = []
        for i in range(100):
            events.append({
                "event_id": f"bulk-large-{i:04d}",
                "event_type": "payment_initiated",
                "transaction_id": f"bulk-txn-{i:04d}",
                "merchant_id": f"merchant-{i % 5}",
                "merchant_name": f"Merchant {i % 5}",
                "amount": 100.00 + i,
                "currency": "INR",
                "timestamp": f"2026-01-15T10:{i // 60:02d}:{i % 60:02d}.000000+00:00"
            })
        
        response = client.post("/events/bulk", json={"events": events})
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_received"] == 100
        assert data["successful"] == 100
        assert data["failed"] == 0
    
    def test_bulk_mixed_transactions(self, client):
        """Test bulk with multiple events per transaction (tests ordering)."""
        events = [
            # Transaction 1 - events out of order
            {
                "event_id": "bulk-mix-003",
                "event_type": "settled",
                "transaction_id": "bulk-mix-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test Merchant",
                "amount": 500.00,
                "currency": "INR",
                "timestamp": "2026-01-15T12:00:00.000000+00:00"
            },
            {
                "event_id": "bulk-mix-001",
                "event_type": "payment_initiated",
                "transaction_id": "bulk-mix-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test Merchant",
                "amount": 500.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "bulk-mix-002",
                "event_type": "payment_processed",
                "transaction_id": "bulk-mix-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test Merchant",
                "amount": 500.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:30:00.000000+00:00"
            },
        ]
        
        response = client.post("/events/bulk", json={"events": events})
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["successful"] == 3
        
        # Verify transaction ended up in correct state
        txn_response = client.get("/transactions/bulk-mix-txn-001")
        assert txn_response.json()["status"] == "settled"
    
    def test_bulk_partial_duplicates(self, client):
        """Test bulk with mix of new and duplicate events."""
        # First, create some events
        first_batch = [
            {
                "event_id": "partial-001",
                "event_type": "payment_initiated",
                "transaction_id": "partial-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            }
        ]
        client.post("/events/bulk", json={"events": first_batch})
        
        # Now send mix of new and duplicate
        mixed_batch = [
            first_batch[0],  # Duplicate
            {
                "event_id": "partial-002",
                "event_type": "payment_processed",
                "transaction_id": "partial-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:05:00.000000+00:00"
            }
        ]
        
        response = client.post("/events/bulk", json={"events": mixed_batch})
        
        data = response.json()
        assert data["total_received"] == 2
        assert data["successful"] == 1
        assert data["duplicates"] == 1
    
    def test_invalid_event_type(self, client):
        """Test rejection of invalid event type."""
        invalid_event = {
            "event_id": "invalid-001",
            "event_type": "invalid_type",
            "transaction_id": "txn-001",
            "merchant_id": "merchant-001",
            "merchant_name": "Test",
            "amount": 100.00,
            "currency": "INR",
            "timestamp": "2026-01-15T10:00:00.000000+00:00"
        }
        
        response = client.post("/events", json=invalid_event)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_amount(self, client, sample_event):
        """Test rejection of invalid amount."""
        sample_event["amount"] = -100.00
        
        response = client.post("/events", json=sample_event)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTransactionStatusUpdate:
    """Test that event ingestion properly updates transaction status."""
    
    def test_status_progression(self, client, sample_events_flow):
        """Test transaction status updates through event flow."""
        # Ingest events one by one
        for event in sample_events_flow:
            client.post("/events", json=event)
        
        # Check final transaction status
        response = client.get(f"/transactions/{sample_events_flow[0]['transaction_id']}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "settled"
        assert data["event_count"] == 3
    
    def test_failed_status(self, client):
        """Test transaction moves to failed status."""
        events = [
            {
                "event_id": "fail-001",
                "event_type": "payment_initiated",
                "transaction_id": "fail-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "fail-002",
                "event_type": "payment_failed",
                "transaction_id": "fail-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:05:00.000000+00:00"
            },
        ]
        
        for event in events:
            client.post("/events", json=event)
        
        response = client.get("/transactions/fail-txn-001")
        assert response.json()["status"] == "failed"
