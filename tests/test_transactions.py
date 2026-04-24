"""
Tests for the Transactions API endpoints.
"""

import pytest
from fastapi import status


class TestTransactionsList:
    """Test cases for listing transactions."""
    
    def test_list_empty_transactions(self, client):
        """Test listing when no transactions exist."""
        response = client.get("/transactions")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["transactions"] == []
        assert data["pagination"]["total_items"] == 0
    
    def test_list_transactions_pagination(self, client, sample_events_flow):
        """Test pagination of transactions."""
        # Create some transactions
        for i in range(5):
            events = [
                {
                    "event_id": f"list-event-{i}",
                    "event_type": "payment_initiated",
                    "transaction_id": f"list-txn-{i}",
                    "merchant_id": "merchant-001",
                    "merchant_name": "Test Merchant",
                    "amount": 1000.00 + i,
                    "currency": "INR",
                    "timestamp": f"2026-01-{15+i}T10:00:00.000000+00:00"
                }
            ]
            client.post("/events/bulk", json={"events": events})
        
        # Test pagination
        response = client.get("/transactions?page=1&page_size=2")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["transactions"]) == 2
        assert data["pagination"]["total_items"] == 5
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["has_next"] == True
    
    def test_filter_by_merchant(self, client):
        """Test filtering transactions by merchant ID."""
        # Create transactions for different merchants
        events = [
            {
                "event_id": "filter-001",
                "event_type": "payment_initiated",
                "transaction_id": "filter-txn-001",
                "merchant_id": "merchant-A",
                "merchant_name": "Merchant A",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "filter-002",
                "event_type": "payment_initiated",
                "transaction_id": "filter-txn-002",
                "merchant_id": "merchant-B",
                "merchant_name": "Merchant B",
                "amount": 200.00,
                "currency": "INR",
                "timestamp": "2026-01-15T11:00:00.000000+00:00"
            },
        ]
        client.post("/events/bulk", json={"events": events})
        
        # Filter by merchant A
        response = client.get("/transactions?merchant_id=merchant-A")
        
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["merchant_id"] == "merchant-A"
    
    def test_filter_by_status(self, client, sample_events_flow):
        """Test filtering transactions by status."""
        # Create a settled transaction
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        # Filter by settled status
        response = client.get("/transactions?status=settled")
        
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["status"] == "settled"


class TestTransactionDetail:
    """Test cases for transaction detail endpoint."""
    
    def test_get_transaction_detail(self, client, sample_events_flow):
        """Test getting transaction details with event history."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        transaction_id = sample_events_flow[0]["transaction_id"]
        response = client.get(f"/transactions/{transaction_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["transaction_id"] == transaction_id
        assert data["merchant"]["id"] == sample_events_flow[0]["merchant_id"]
        assert data["merchant"]["name"] == sample_events_flow[0]["merchant_name"]
        assert data["event_count"] == 3
        assert len(data["events"]) == 3
    
    def test_transaction_not_found(self, client):
        """Test 404 for non-existent transaction."""
        response = client.get("/transactions/non-existent-id")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_events_sorted_by_timestamp(self, client, sample_events_flow):
        """Test that events are returned sorted by timestamp (oldest first)."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        transaction_id = sample_events_flow[0]["transaction_id"]
        response = client.get(f"/transactions/{transaction_id}")
        
        data = response.json()
        events = data["events"]
        
        # Verify events are sorted by timestamp (ascending)
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)
        
        # Verify event sequence
        assert events[0]["event_type"] == "payment_initiated"
        assert events[1]["event_type"] == "payment_processed"
        assert events[2]["event_type"] == "settled"
    
    def test_transaction_detail_has_all_fields(self, client, sample_events_flow):
        """Test that transaction detail response has all expected fields."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        transaction_id = sample_events_flow[0]["transaction_id"]
        response = client.get(f"/transactions/{transaction_id}")
        
        data = response.json()
        
        # Verify all required fields are present
        assert "transaction_id" in data
        assert "merchant" in data
        assert "id" in data["merchant"]
        assert "name" in data["merchant"]
        assert "amount" in data
        assert "currency" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "event_count" in data
        assert "events" in data
        
        # Verify event fields
        for event in data["events"]:
            assert "event_id" in event
            assert "event_type" in event
            assert "timestamp" in event
    
    def test_transaction_detail_with_single_event(self, client):
        """Test transaction detail with only initiation event."""
        event = {
            "event_id": "single-evt-001",
            "event_type": "payment_initiated",
            "transaction_id": "single-txn-001",
            "merchant_id": "merchant-001",
            "merchant_name": "Single Event Merchant",
            "amount": 500.00,
            "currency": "INR",
            "timestamp": "2026-01-15T10:00:00.000000+00:00"
        }
        client.post("/events", json=event)
        
        response = client.get("/transactions/single-txn-001")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "initiated"
        assert data["event_count"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "payment_initiated"
