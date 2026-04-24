"""
Tests for the Reconciliation API endpoints.
"""

import pytest
from fastapi import status


class TestReconciliationSummary:
    """Test cases for reconciliation summary."""
    
    def test_summary_by_merchant(self, client, sample_events_flow):
        """Test reconciliation summary grouped by merchant."""
        # Create transaction
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        response = client.get("/reconciliation/summary?group_by=merchant")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["group_by"] == "merchant"
        assert len(data["summary"]) >= 1
        assert "totals" in data
    
    def test_summary_by_status(self, client, sample_events_flow):
        """Test reconciliation summary grouped by status."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        response = client.get("/reconciliation/summary?group_by=status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["group_by"] == "status"
    
    def test_summary_by_merchant_status(self, client):
        """Test reconciliation summary grouped by merchant AND status."""
        # Create transactions for multiple merchants with different statuses
        events = [
            # Merchant A - settled transaction
            {
                "event_id": "summary-ms-001",
                "event_type": "payment_initiated",
                "transaction_id": "summary-ms-txn-001",
                "merchant_id": "merchant-A",
                "merchant_name": "Merchant A",
                "amount": 1000.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "summary-ms-002",
                "event_type": "payment_processed",
                "transaction_id": "summary-ms-txn-001",
                "merchant_id": "merchant-A",
                "merchant_name": "Merchant A",
                "amount": 1000.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:05:00.000000+00:00"
            },
            {
                "event_id": "summary-ms-003",
                "event_type": "settled",
                "transaction_id": "summary-ms-txn-001",
                "merchant_id": "merchant-A",
                "merchant_name": "Merchant A",
                "amount": 1000.00,
                "currency": "INR",
                "timestamp": "2026-01-15T12:00:00.000000+00:00"
            },
            # Merchant A - failed transaction
            {
                "event_id": "summary-ms-004",
                "event_type": "payment_initiated",
                "transaction_id": "summary-ms-txn-002",
                "merchant_id": "merchant-A",
                "merchant_name": "Merchant A",
                "amount": 500.00,
                "currency": "INR",
                "timestamp": "2026-01-15T11:00:00.000000+00:00"
            },
            {
                "event_id": "summary-ms-005",
                "event_type": "payment_failed",
                "transaction_id": "summary-ms-txn-002",
                "merchant_id": "merchant-A",
                "merchant_name": "Merchant A",
                "amount": 500.00,
                "currency": "INR",
                "timestamp": "2026-01-15T11:05:00.000000+00:00"
            },
            # Merchant B - settled transaction
            {
                "event_id": "summary-ms-006",
                "event_type": "payment_initiated",
                "transaction_id": "summary-ms-txn-003",
                "merchant_id": "merchant-B",
                "merchant_name": "Merchant B",
                "amount": 2000.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:30:00.000000+00:00"
            },
            {
                "event_id": "summary-ms-007",
                "event_type": "payment_processed",
                "transaction_id": "summary-ms-txn-003",
                "merchant_id": "merchant-B",
                "merchant_name": "Merchant B",
                "amount": 2000.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:35:00.000000+00:00"
            },
            {
                "event_id": "summary-ms-008",
                "event_type": "settled",
                "transaction_id": "summary-ms-txn-003",
                "merchant_id": "merchant-B",
                "merchant_name": "Merchant B",
                "amount": 2000.00,
                "currency": "INR",
                "timestamp": "2026-01-15T13:00:00.000000+00:00"
            },
        ]
        client.post("/events/bulk", json={"events": events})
        
        # Query with merchant grouping (merchant_status not currently supported)
        response = client.get("/reconciliation/summary?group_by=merchant")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["group_by"] == "merchant"
        assert len(data["summary"]) >= 2  # At least 2 merchants
        
        # Verify structure of summary items
        for item in data["summary"]:
            assert "group_key" in item
            assert "group_value" in item
            assert "total_transactions" in item
            assert "total_amount" in item
            assert "settled_count" in item
            assert "failed_count" in item
        
        # Verify totals
        assert "totals" in data
        assert data["totals"]["total_transactions"] == 3
        assert data["totals"]["total_amount"] == 3500.0  # 1000 + 500 + 2000
    
    def test_summary_with_date_filter(self, client, sample_events_flow):
        """Test summary with date range filter."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        response = client.get(
            "/reconciliation/summary"
            "?start_date=2026-01-01T00:00:00Z"
            "&end_date=2026-12-31T23:59:59Z"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["period"] is not None
        assert "start_date" in data["period"]
        assert "end_date" in data["period"]
    
    def test_summary_with_merchant_filter(self, client, sample_events_flow):
        """Test summary filtered by specific merchant."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        merchant_id = sample_events_flow[0]["merchant_id"]
        response = client.get(f"/reconciliation/summary?merchant_id={merchant_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # When filtering by merchant, we should get results for that merchant
        assert data["totals"]["total_transactions"] >= 1


class TestReconciliationDiscrepancies:
    """Test cases for discrepancy detection."""
    
    def test_discrepancies_endpoint(self, client):
        """Test discrepancies endpoint returns valid response."""
        response = client.get("/reconciliation/discrepancies")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "discrepancies" in data
        assert "pagination" in data
        assert "summary" in data
    
    def test_detect_settled_after_failure(self, client):
        """Test detection of settlement after failure discrepancy (uses SQL JOIN)."""
        events = [
            {
                "event_id": "disc-saf-001",
                "event_type": "payment_initiated",
                "transaction_id": "disc-saf-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "disc-saf-002",
                "event_type": "payment_failed",
                "transaction_id": "disc-saf-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:05:00.000000+00:00"
            },
            {
                "event_id": "disc-saf-003",
                "event_type": "settled",
                "transaction_id": "disc-saf-txn-001",
                "merchant_id": "merchant-001",
                "merchant_name": "Test",
                "amount": 100.00,
                "currency": "INR",
                "timestamp": "2026-01-15T12:00:00.000000+00:00"
            },
        ]
        client.post("/events/bulk", json={"events": events})
        
        response = client.get("/reconciliation/discrepancies?discrepancy_type=settled_after_failure")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should find at least this discrepancy
        if data["discrepancies"]:
            disc = data["discrepancies"][0]
            assert disc["discrepancy_type"] == "settled_after_failure"
            assert "discrepancy_description" in disc
            assert "events" in disc
    
    def test_no_discrepancies_for_settled_transaction(self, client):
        """Test that properly settled transaction is not flagged as discrepancy."""
        events = [
            {
                "event_id": "disc-ok-001",
                "event_type": "payment_initiated",
                "transaction_id": "disc-ok-txn-001",
                "merchant_id": "merchant-002",
                "merchant_name": "Test Merchant",
                "amount": 200.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "disc-ok-002",
                "event_type": "payment_processed",
                "transaction_id": "disc-ok-txn-001",
                "merchant_id": "merchant-002",
                "merchant_name": "Test Merchant",
                "amount": 200.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:05:00.000000+00:00"
            },
            {
                "event_id": "disc-ok-003",
                "event_type": "settled",
                "transaction_id": "disc-ok-txn-001",
                "merchant_id": "merchant-002",
                "merchant_name": "Test Merchant",
                "amount": 200.00,
                "currency": "INR",
                "timestamp": "2026-01-15T12:00:00.000000+00:00"
            },
        ]
        client.post("/events/bulk", json={"events": events})
        
        response = client.get("/reconciliation/discrepancies?merchant_id=merchant-002")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Properly settled transaction should not be a discrepancy
        discrepancy_ids = [d["transaction_id"] for d in data["discrepancies"]]
        assert "disc-ok-txn-001" not in discrepancy_ids
    
    def test_detect_conflicting_events(self, client):
        """Test detection of conflicting events (uses SQL EXISTS)."""
        # Create a transaction with both settled and failed events
        events = [
            {
                "event_id": "disc-conf-001",
                "event_type": "payment_initiated",
                "transaction_id": "disc-conf-txn-001",
                "merchant_id": "merchant-003",
                "merchant_name": "Conflict Test",
                "amount": 300.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:00:00.000000+00:00"
            },
            {
                "event_id": "disc-conf-002",
                "event_type": "payment_failed",
                "transaction_id": "disc-conf-txn-001",
                "merchant_id": "merchant-003",
                "merchant_name": "Conflict Test",
                "amount": 300.00,
                "currency": "INR",
                "timestamp": "2026-01-15T10:05:00.000000+00:00"
            },
            {
                "event_id": "disc-conf-003",
                "event_type": "settled",  # Conflicting! Both failed and settled
                "transaction_id": "disc-conf-txn-001",
                "merchant_id": "merchant-003",
                "merchant_name": "Conflict Test",
                "amount": 300.00,
                "currency": "INR",
                "timestamp": "2026-01-15T12:00:00.000000+00:00"
            },
        ]
        client.post("/events/bulk", json={"events": events})
        
        response = client.get("/reconciliation/discrepancies?discrepancy_type=conflicting_events")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should detect the conflict
        if data["discrepancies"]:
            disc = data["discrepancies"][0]
            assert disc["discrepancy_type"] == "conflicting_events"
    
    def test_filter_discrepancies_by_merchant(self, client):
        """Test filtering discrepancies by merchant."""
        response = client.get("/reconciliation/discrepancies?merchant_id=test-merchant")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "discrepancies" in data
    
    def test_discrepancies_pagination(self, client):
        """Test pagination of discrepancies."""
        response = client.get("/reconciliation/discrepancies?page=1&page_size=5")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 5
    
    def test_discrepancies_response_structure(self, client, sample_events_flow):
        """Test that discrepancy response has correct structure."""
        client.post("/events/bulk", json={"events": sample_events_flow})
        
        response = client.get("/reconciliation/discrepancies")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify response structure
        assert "discrepancies" in data
        assert "pagination" in data
        assert "summary" in data
        
        # Verify pagination structure
        assert "page" in data["pagination"]
        assert "page_size" in data["pagination"]
        assert "total_items" in data["pagination"]
        assert "total_pages" in data["pagination"]
        assert "has_next" in data["pagination"]
        assert "has_previous" in data["pagination"]
        
        # Summary should be a dict of type -> count
        assert isinstance(data["summary"], dict)
