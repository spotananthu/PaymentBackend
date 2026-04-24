# Payment Reconciliation Service

A backend service for processing payment lifecycle events, managing transaction state, and generating reconciliation reports.

## Quick Start

```bash
# Local development
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://localhost:5432/payment_reconciliation
uvicorn app.main:app --reload
```

**Then open:** http://localhost:8000/docs (Interactive API documentation)

---

## 📊 Sample Data

The provided `sample_events.json` contains **10,355 events** across **5 merchants** with realistic scenarios:

| Metric | Value |
|--------|-------|
| Total events | 10,355 |
| Merchants | 5 (QuickMart, FreshBasket, UrbanEats, TechBazaar, StyleHub) |
| Transactions | ~3,800 |
| Successful flows | ✅ initiated → processed → settled |
| Failed transactions | ✅ initiated → failed |
| Pending settlements | ✅ processed but not settled |
| Duplicate events | ✅ Same event_id submitted multiple times |
| Discrepancies | ✅ Settled after failure, stuck in processed |

### Loading Sample Data

```bash
# Option 1: Use the bulk endpoint (via curl)
curl -X POST http://localhost:8000/events/bulk \
  -H "Content-Type: application/json" \
  -d "{\"events\": $(cat sample_events.json)}"

# Option 2: Use the interactive API docs
# Open http://localhost:8000/docs → POST /events/bulk → Upload JSON
```

### Expected Results After Loading

```bash
# Check transaction stats
curl http://localhost:8000/reconciliation/summary

# Response shows:
# - ~3,800 transactions
# - ~42% settlement rate  
# - ~300+ discrepancies detected
```

---

## 🔐 Idempotency (Critical Design)

Duplicate event handling is **guaranteed** at three levels:

1. **Application check**: Pre-query before insert returns early for duplicates
2. **Database constraint**: `event_id` is PRIMARY KEY — DB rejects duplicates  
3. **Race condition handling**: `IntegrityError` caught, returns existing event

```python
# Simplified flow (event_service.py)
existing = db.get(Event, event_id)
if existing:
    return response(is_duplicate=True)  # ← No state update, returns early

try:
    db.add(event)
    update_status(...)  # ← Only runs if insert succeeds
    db.commit()
except IntegrityError:
    return response(is_duplicate=True)  # ← Concurrent duplicate handled
```

**Guarantee**: Submitting the same event twice will:
- ❌ NOT create duplicate records
- ❌ NOT update transaction state
- ✅ Return `is_duplicate: true` safely

---

## 🗄️ SQL Query Design

All filtering, pagination, and aggregation execute at the **database level** using SQLAlchemy Core queries that compile to optimized SQL.

### Transaction Listing
```python
# Compiles to: SELECT ... WHERE status = ? AND merchant_id = ? ORDER BY created_at LIMIT ? OFFSET ?
query = select(Transaction)
    .where(Transaction.status == status)
    .where(Transaction.merchant_id == merchant_id)
    .order_by(desc(Transaction.created_at))
    .offset(offset).limit(page_size)
```

### Reconciliation Summary
```python
# Compiles to: SELECT merchant_id, COUNT(*), SUM(CASE WHEN status='settled' THEN 1 END) ... GROUP BY merchant_id
query = select(
    Transaction.merchant_id,
    func.count(Transaction.id),
    func.sum(case((Transaction.status == 'settled', 1), else_=0))
).group_by(Transaction.merchant_id)
```

### Discrepancy Detection
```python
# Compiles to: SELECT ... WHERE NOT EXISTS (SELECT 1 FROM events WHERE event_type='settled' AND ...)
settled_exists = select(Event.id).where(Event.event_type == 'settled').exists()
query = select(Transaction).where(~settled_exists)
```

---

## 📊 Database Indexes

Composite indexes designed based on actual query patterns:

```sql
-- Single column indexes
CREATE INDEX ix_transactions_status ON transactions(status);
CREATE INDEX ix_transactions_created_at ON transactions(created_at);
CREATE INDEX ix_events_transaction_id ON events(transaction_id);

-- Composite indexes for common query patterns
CREATE INDEX ix_transactions_merchant_status ON transactions(merchant_id, status);
CREATE INDEX ix_transactions_merchant_created ON transactions(merchant_id, created_at);
CREATE INDEX ix_transactions_status_created ON transactions(status, created_at);
CREATE INDEX ix_events_transaction_timestamp ON events(transaction_id, timestamp);
```

---

## ⚖️ Trade-offs & Decisions

| Decision | Rationale | Alternative |
|----------|-----------|-------------|
| **Event ID as PK** | Database-level idempotency, no extra unique index needed | Separate UUID + unique constraint |
| **Denormalized merchant_id in events** | Faster queries without JOIN through transactions | Normalize and JOIN |
| **In-memory discrepancy pagination** | Low expected volume (<1% of transactions), simpler queries | SQL window functions with LIMIT/OFFSET |
| **Sync processing** | Simpler implementation, adequate for expected load | Async with Celery for higher throughput |
| **State machine in code** | Explicit transitions, easy to test and audit | Database triggers |

### Discrepancy Pagination Note
Discrepancy pagination currently happens in Python after SQL filtering. This was a **conscious tradeoff** to keep query complexity manageable. The SQL query itself uses WHERE clauses and EXISTS subqueries for filtering. For production scale, this could be moved to SQL using window functions.

---

## 🛡️ Edge Cases Handled

| Edge Case | How It's Handled |
|-----------|------------------|
| **Duplicate event ingestion** | Returns `is_duplicate: true` without state mutation |
| **Invalid state transitions** | State machine rejects (e.g., `FAILED` → `SETTLED`) |
| **Out-of-order events** | Events sorted by timestamp before processing |
| **Concurrent duplicate submission** | `IntegrityError` caught, returns existing event |
| **Terminal state protection** | No transitions allowed from `SETTLED` or `FAILED` |
| **Null status prevention** | State machine returns `new_status=None` for no-op, code checks before assignment |

**Example: Duplicate handling in production**
```
Request 1: POST /events {event_id: "evt-001"} → 201 Created, is_duplicate: false
Request 2: POST /events {event_id: "evt-001"} → 200 OK, is_duplicate: true  ← No state change
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI                                  │
├─────────────────────────────────────────────────────────────────┤
│  API Layer                                                       │
│  ├── POST /events         → Ingest events (idempotent)          │
│  ├── GET  /transactions   → Query with filters                  │
│  └── GET  /reconciliation → Summaries & discrepancies           │
├─────────────────────────────────────────────────────────────────┤
│  Service Layer (Business Logic + SQL)                            │
│  ├── EventService         → Idempotency, state machine          │
│  ├── TransactionService   → Queries, pagination                 │
│  └── ReconciliationService→ Aggregations, anomaly detection     │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer (PostgreSQL)                                         │
│  ├── merchants            → Partner information                 │
│  ├── transactions         → Current state (derived)             │
│  └── events               → Immutable audit log                 │
└─────────────────────────────────────────────────────────────────┘
```

**Transaction State Machine:**
```
INITIATED → PROCESSED → SETTLED
     ↓          ↓
   FAILED ←────┘
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/events` | Ingest event (idempotent) |
| `POST` | `/events/bulk` | Bulk ingest (10k+ optimized) |
| `GET` | `/transactions` | List with filters/pagination |
| `GET` | `/transactions/{id}` | Details with event history |
| `GET` | `/reconciliation/summary` | Aggregated stats by merchant/status |
| `GET` | `/reconciliation/discrepancies` | Find anomalies |

### Example: Event Ingestion
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt-001",
    "event_type": "payment_initiated",
    "transaction_id": "txn-001",
    "merchant_id": "merchant-001",
    "merchant_name": "TechMart",
    "amount": 1500.00,
    "currency": "INR",
    "timestamp": "2026-01-15T10:30:00Z"
  }'
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Key test cases covered:
# - Duplicate event handling (idempotency)
# - Bulk ingestion with duplicates
# - Transaction state transitions
# - Discrepancy detection scenarios
```

Postman collection included: `postman_collection.json`

---

## 📁 Project Structure

```
app/
├── api/v1/           # Route handlers
├── core/             # Config, database, state machine
├── models/           # SQLAlchemy models (with indexes)
├── schemas/          # Pydantic validation
├── services/         # Business logic + SQL queries
└── main.py
tests/                # Pytest test suite
scripts/              # Sample data generation
```

---

## 🚀 Setup & Deployment

### Local Development
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://localhost:5432/payment_reconciliation
uvicorn app.main:app --reload
# App: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 🌐 Live Deployment

**Production URL:** `https://[YOUR-APP].onrender.com`

Deployed on [Render](https://render.com) with managed PostgreSQL.

#### Deploy Your Own:

1. Push code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New → Blueprint** and connect your repo
4. Render auto-detects `render.yaml` and provisions the database + web service
5. Wait for build & deploy to complete

Or deploy manually:
```bash
# 1. Create a PostgreSQL database on Render (Free tier)
#    Dashboard → New → PostgreSQL → Copy the External Database URL

# 2. Create a Web Service
#    Dashboard → New → Web Service → Connect your GitHub repo
#    Build Command: (uses Dockerfile automatically)
#    Environment: Docker

# 3. Add environment variable
#    DATABASE_URL = <paste the Internal Database URL from step 1>
```

The app auto-configures via `DATABASE_URL` environment variable provided by Render.

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `APP_ENV` | Environment (development/production) | development |
| `DEBUG` | Enable debug logging | false |

---

## Tech Stack

| Technology | Why |
|------------|-----|
| **FastAPI** | Auto OpenAPI docs, Pydantic integration, async-ready |
| **PostgreSQL** | ACID transactions, robust aggregations, mature indexing |
| **SQLAlchemy 2.0** | Type-safe, compiles to optimized SQL |
| **Pydantic v2** | 5-50x faster validation than v1 |

---

**Built for Setu Solutions Engineer Assessment**
