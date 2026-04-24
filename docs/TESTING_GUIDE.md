# API Testing Guide

Step-by-step curl commands to test every endpoint. All commands use the live production instance with sample data already loaded.

Set the base URL:

```bash
BASE=https://payment-reconciliation-api-53vz.onrender.com
```

Append `| python3 -m json.tool` to any command for formatted output.

---

## 1. Health Check

```bash
curl -s $BASE/health
```

Expected: `{"status": "healthy", "service": "payment-reconciliation"}`

---

## 2. Event Ingestion

Ingest a new event:

```bash
curl -s -X POST $BASE/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-evt-001",
    "event_type": "payment_initiated",
    "transaction_id": "test-txn-001",
    "merchant_id": "merchant_1",
    "merchant_name": "QuickMart",
    "amount": 2500.00,
    "currency": "INR",
    "timestamp": "2026-04-24T10:00:00Z"
  }'
```

Expected: `"is_duplicate": false`, new transaction created with status `initiated`.

---

## 3. Idempotency

Submit the exact same event again:

```bash
curl -s -X POST $BASE/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-evt-001",
    "event_type": "payment_initiated",
    "transaction_id": "test-txn-001",
    "merchant_id": "merchant_1",
    "merchant_name": "QuickMart",
    "amount": 2500.00,
    "currency": "INR",
    "timestamp": "2026-04-24T10:00:00Z"
  }'
```

Expected: `"is_duplicate": true`. No new record created, no state change.

---

## 4. State Progression

Move the transaction through the full lifecycle: initiated -> processed -> settled.

**Process the payment:**

```bash
curl -s -X POST $BASE/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-evt-002",
    "event_type": "payment_processed",
    "transaction_id": "test-txn-001",
    "merchant_id": "merchant_1",
    "merchant_name": "QuickMart",
    "amount": 2500.00,
    "currency": "INR",
    "timestamp": "2026-04-24T10:05:00Z"
  }'
```

Expected: transaction status updates to `processed`.

**Settle the payment:**

```bash
curl -s -X POST $BASE/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-evt-003",
    "event_type": "settled",
    "transaction_id": "test-txn-001",
    "merchant_id": "merchant_1",
    "merchant_name": "QuickMart",
    "amount": 2500.00,
    "currency": "INR",
    "timestamp": "2026-04-24T10:10:00Z"
  }'
```

Expected: transaction status updates to `settled` (terminal state).

---

## 5. Transaction Detail

Fetch the transaction with its full event history:

```bash
curl -s "$BASE/transactions/test-txn-001"
```

Expected: transaction object with status `settled`, merchant info, and 3 events sorted by timestamp.

---

## 6. Transaction Listing -- Filters

**Filter by merchant and status:**

```bash
curl -s "$BASE/transactions?merchant_id=merchant_1&status=settled&page_size=5"
```

**Sort by amount descending:**

```bash
curl -s "$BASE/transactions?sort_by=amount&sort_order=desc&page_size=5"
```

**Date range filter:**

```bash
curl -s "$BASE/transactions?start_date=2026-01-01&end_date=2026-01-31&page_size=5"
```

**Pagination:**

```bash
curl -s "$BASE/transactions?page=1&page_size=10"
curl -s "$BASE/transactions?page=2&page_size=10"
```

Expected: paginated results with `pagination.total_items`, `has_next`, `has_previous`.

---

## 7. Reconciliation Summary

**Group by merchant:**

```bash
curl -s "$BASE/reconciliation/summary?group_by=merchant"
```

**Group by status:**

```bash
curl -s "$BASE/reconciliation/summary?group_by=status"
```

**Group by date:**

```bash
curl -s "$BASE/reconciliation/summary?group_by=date"
```

**Group by merchant + status (combined):**

```bash
curl -s "$BASE/reconciliation/summary?group_by=merchant_status"
```

Expected: each response contains per-group breakdowns with counts, amounts, and settlement rates. Totals section shows overall stats (~3,800 transactions, ~67.5% settlement rate).

---

## 8. Discrepancy Detection

**All discrepancies (with summary counts):**

```bash
curl -s "$BASE/reconciliation/discrepancies?page_size=5"
```

Expected: `summary` field shows counts per type:
- processed_not_settled: 380
- settled_after_failure: 95
- duplicate_settlement: 95
- conflicting_events: 95
- missing_initiation: 0

**Filter by discrepancy type:**

```bash
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=processed_not_settled&page_size=5"
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=settled_after_failure&page_size=5"
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=duplicate_settlement&page_size=5"
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=conflicting_events&page_size=5"
```

**Filter by merchant:**

```bash
curl -s "$BASE/reconciliation/discrepancies?merchant_id=merchant_2&page_size=5"
```

**Combined filters:**

```bash
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=settled_after_failure&merchant_id=merchant_3&page_size=5"
```

Each discrepancy includes the transaction_id, merchant info, amount, current status, discrepancy type, description, and the full event timeline.

---

## 9. Bulk Ingestion

To load the full sample dataset (10,355 events) into a fresh instance:

```bash
curl -s -X POST $BASE/events/bulk \
  -H "Content-Type: application/json" \
  -d "{\"events\": $(cat sample_events.json)}"
```

Expected: ~10,165 successful, ~190 duplicates detected and skipped, 0 failures.

---

## Alternative: Postman

Import [postman_collection.json](postman_collection.json) into Postman for a GUI-based testing experience with all endpoints pre-configured.
