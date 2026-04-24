# Payment Reconciliation Service

**Live:** https://payment-reconciliation-api-53vz.onrender.com
**Docs:** https://payment-reconciliation-api-53vz.onrender.com/docs
**Repo:** https://github.com/spotananthu/PaymentBackend

---

## Overview

A backend service that ingests payment lifecycle events, derives transaction state through a state machine, and generates reconciliation reports with discrepancy detection.

Built with FastAPI, PostgreSQL, SQLAlchemy 2.0, and Pydantic v2.

---

## Setup

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://localhost:5432/payment_reconciliation
uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

### Deploy (Render)

Push to GitHub, then on Render: New > Blueprint > select repo. The `render.yaml` provisions a free PostgreSQL instance and a Docker web service automatically. No manual env vars needed.

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /events | Ingest a single event (idempotent) |
| POST | /events/bulk | Bulk ingest up to 50,000 events |
| GET | /transactions | List transactions with filtering, sorting, pagination |
| GET | /transactions/{id} | Transaction detail with full event history |
| GET | /reconciliation/summary | Aggregated stats grouped by merchant, status, date, or merchant+status |
| GET | /reconciliation/discrepancies | Detect anomalies across transactions |
| GET | /health | Service health check |

### Event Ingestion

```bash
curl -X POST https://payment-reconciliation-api-53vz.onrender.com/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt-001",
    "event_type": "payment_initiated",
    "transaction_id": "txn-001",
    "merchant_id": "merchant_1",
    "merchant_name": "QuickMart",
    "amount": 1500.00,
    "currency": "INR",
    "timestamp": "2026-01-15T10:30:00Z"
  }'
```

Submitting the same `event_id` again returns `is_duplicate: true` without mutating state.

### Transaction Queries

```
GET /transactions?status=settled&merchant_id=merchant_1&sort_by=amount&sort_order=desc&page=1&page_size=20
GET /transactions?start_date=2026-01-01&end_date=2026-01-31
```

Returns paginated results with `pagination.total_items`, `has_next`, `has_previous`.

### Reconciliation

```
GET /reconciliation/summary?group_by=merchant
GET /reconciliation/summary?group_by=status
GET /reconciliation/summary?group_by=date
GET /reconciliation/summary?group_by=merchant_status
```

Each returns per-group counts, amounts, and settlement rates. All aggregation runs in SQL via GROUP BY, COUNT, SUM, and CASE expressions.

### Discrepancy Detection

```
GET /reconciliation/discrepancies?discrepancy_type=settled_after_failure&merchant_id=merchant_2&page_size=50
```

Five discrepancy types:

| Type | Meaning |
|------|---------|
| processed_not_settled | Transaction reached "processed" but never "settled" |
| settled_after_failure | Settlement event recorded after a failure event |
| duplicate_settlement | Multiple settlement events for the same transaction |
| missing_initiation | Processing/settlement events exist without an initiation event |
| conflicting_events | Both failure and settlement events on the same transaction |

Detection uses SQL subqueries with EXISTS/NOT EXISTS. No Python-side iteration over rows.

---

## Quick Test (curl)

All commands use the live production instance. Sample data is already loaded.

```bash
BASE=https://payment-reconciliation-api-53vz.onrender.com

# 1. Health check
curl -s $BASE/health

# 2. Ingest a single event
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

# 3. Idempotency -- same event_id returns is_duplicate: true
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

# 4. Progress the transaction: processed then settled
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

# 5. Get transaction detail with full event history
curl -s "$BASE/transactions/test-txn-001"

# 6. List transactions -- filter by merchant and status
curl -s "$BASE/transactions?merchant_id=merchant_1&status=settled&page_size=5"

# 7. List transactions -- sort by amount descending
curl -s "$BASE/transactions?sort_by=amount&sort_order=desc&page_size=5"

# 8. List transactions -- date range filter
curl -s "$BASE/transactions?start_date=2026-01-01&end_date=2026-01-31&page_size=5"

# 9. Reconciliation summary -- group by merchant
curl -s "$BASE/reconciliation/summary?group_by=merchant"

# 10. Reconciliation summary -- group by status
curl -s "$BASE/reconciliation/summary?group_by=status"

# 11. Reconciliation summary -- group by date
curl -s "$BASE/reconciliation/summary?group_by=date"

# 12. Reconciliation summary -- group by merchant + status
curl -s "$BASE/reconciliation/summary?group_by=merchant_status"

# 13. Discrepancies -- all types with summary counts
curl -s "$BASE/reconciliation/discrepancies?page_size=5"

# 14. Discrepancies -- filter by type
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=settled_after_failure&page_size=5"

# 15. Discrepancies -- filter by merchant
curl -s "$BASE/reconciliation/discrepancies?merchant_id=merchant_2&page_size=5"

# 16. Discrepancies -- filter by type and merchant
curl -s "$BASE/reconciliation/discrepancies?discrepancy_type=duplicate_settlement&merchant_id=merchant_3&page_size=5"
```

Pipe any command through `| python3 -m json.tool` for formatted output.

---

## Design Decisions

### Idempotency

`event_id` is the primary key of the events table. Duplicate handling at three levels:

1. **Bulk deduplication** -- within a single bulk request, duplicate event_ids are collapsed before hitting the database.
2. **Application check** -- a SELECT pre-filters IDs that already exist.
3. **Database constraint** -- PK constraint rejects duplicates even under concurrent writes. IntegrityError is caught and handled gracefully.

No duplicate event creates a new record or triggers a state transition.

### State Machine

Transaction status is derived from events using explicit transition rules:

```
INITIATED --> PROCESSED --> SETTLED
    |              |
    v              v
  FAILED        FAILED
```

SETTLED and FAILED are terminal states. Out-of-order events are sorted by timestamp before processing. Invalid transitions (e.g. FAILED to SETTLED) are rejected; the event is stored but does not change transaction status.

### Database Schema

Three tables: `merchants`, `transactions`, `events`.

- `event_id` as PK gives idempotency without an extra unique index.
- `merchant_id` is denormalized on events to avoid JOINs through transactions for merchant-scoped queries.
- Composite indexes match actual query patterns:

```sql
ix_transactions_merchant_status  (merchant_id, status)
ix_transactions_merchant_created (merchant_id, created_at)
ix_transactions_status_created   (status, created_at)
ix_events_transaction_timestamp  (transaction_id, timestamp)
```

Full ER diagram and schema in `docs/DATABASE_DESIGN.md`.

### SQL-Level Operations

All filtering, pagination, sorting, and aggregation compile to SQL through SQLAlchemy. No data is pulled into Python for processing.

- Transaction listing: `WHERE status = ? AND merchant_id = ? ORDER BY created_at LIMIT ? OFFSET ?`
- Summary by merchant: `SELECT merchant_id, COUNT(*), SUM(amount), SUM(CASE WHEN status='settled' ...) GROUP BY merchant_id`
- Discrepancy detection: `WHERE status = 'processed' AND NOT EXISTS (SELECT 1 FROM events WHERE event_type = 'settled' ...)`

### Trade-offs

| Decision | Rationale | Alternative considered |
|----------|-----------|----------------------|
| event_id as PK | DB-level idempotency, no extra index | Surrogate PK + unique constraint |
| Denormalized merchant_id on events | Avoids JOIN for merchant-scoped queries | Normalized FK through transactions |
| Sync processing | Simpler; adequate for assessment-scale load | Async with background workers |
| In-code state machine | Explicit, testable, auditable | Database triggers |
| Discrepancy pagination in Python | Keeps SQL queries simpler for multi-type detection | Window functions with LIMIT/OFFSET |

---

## Sample Data

`sample_events.json` contains 10,355 events across 5 merchants with intentional scenarios:

- Normal flows (initiated > processed > settled)
- Failed transactions
- Transactions stuck in "processed" (never settled)
- Settlement after failure
- Duplicate event_ids (tests idempotency)

Load into a running instance:

```bash
curl -X POST http://localhost:8000/events/bulk \
  -H "Content-Type: application/json" \
  -d "{\"events\": $(cat sample_events.json)}"
```

After loading: ~3,800 transactions, 67.5% settlement rate, 665 discrepancies (380 processed_not_settled, 95 settled_after_failure, 95 duplicate_settlement, 95 conflicting_events).

The production instance already has this data loaded.

---

## Testing

```bash
pytest tests/ -v
```

34 tests covering:

- Single and bulk event ingestion
- Idempotency (duplicate rejection)
- State transitions (valid and invalid)
- Transaction filtering, sorting, pagination
- Reconciliation summary (all 4 group_by modes)
- Discrepancy detection (all 5 types)
- Edge cases: empty results, not found, invalid input

Tests use an in-memory SQLite database. No external dependencies needed.

Postman collection included at `postman_collection.json`.

---

## Project Structure

```
app/
  main.py                       Entry point, lifespan handler
  core/
    config.py                   Pydantic settings, DATABASE_URL rewrite
    database.py                 Engine, session management
    state_machine.py            Transition rules, event-to-status mapping
  models/
    entities.py                 Merchant, Transaction, Event models
  schemas/
    event.py                    Ingestion request/response
    transaction.py              Query params, detail response
    reconciliation.py           Summary, discrepancy response
    common.py                   Shared pagination
  repositories/
    event_repository.py         Event CRUD
    transaction_repository.py   Filtered queries, sorting
    merchant_repository.py      Auto-create on first event
    reconciliation_repository.py  Aggregation queries
  services/
    event_service.py            Idempotent ingestion, bulk processing
    transaction_service.py      Query orchestration
    reconciliation_service.py   Summary generation, discrepancy detection
  api/v1/
    events.py                   POST /events, POST /events/bulk
    transactions.py             GET /transactions, GET /transactions/{id}
    reconciliation.py           GET /reconciliation/summary, /discrepancies
    health.py                   GET /health
tests/                          34 pytest tests
scripts/                        Sample data generation
docs/                           Database design documentation
```

---

## Tech Stack

- **FastAPI** -- auto-generated OpenAPI docs, Pydantic integration, dependency injection
- **PostgreSQL** -- ACID transactions, aggregation functions, composite indexing
- **SQLAlchemy 2.0** -- compiled SQL queries, type-safe ORM
- **Pydantic v2** -- request/response validation
- **psycopg 3** -- PostgreSQL driver
- **Docker** -- multi-stage production build

---

## AI Disclosure

This project was developed with assistance from AI tool(Copilot) for debugging and documentation. All code was developed, reviewed, tested, and validated manually.
