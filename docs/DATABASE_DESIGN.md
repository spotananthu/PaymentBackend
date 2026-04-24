# Database Schema Design

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PAYMENT EVENT PROCESSING SYSTEM                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐         ┌─────────────────────────┐
│     MERCHANTS       │         │      TRANSACTIONS       │
├─────────────────────┤         ├─────────────────────────┤
│ PK id VARCHAR(50)   │◄───────┤│ PK id VARCHAR(50)       │
│    name VARCHAR(255)│    1:N ││ FK merchant_id          │──┐
│    created_at       │         │    amount NUMERIC(15,2) │  │
│    updated_at       │         │    currency VARCHAR(3)  │  │
└─────────────────────┘         │    status ENUM          │  │
         │                      │    created_at           │  │
         │                      │    updated_at           │  │
         │                      └─────────────────────────┘  │
         │                                  │                │
         │                                  │ 1:N            │
         │                                  ▼                │
         │                      ┌─────────────────────────┐  │
         │                      │        EVENTS           │  │
         │                      ├─────────────────────────┤  │
         │                      │ PK id VARCHAR(50)       │  │
         │              ┌──────►│ FK transaction_id       │  │
         │              │       │ FK merchant_id          │◄─┘
         └──────────────┼──────►│    event_type ENUM      │
                    1:N │       │    amount NUMERIC(15,2) │
                        │       │    currency VARCHAR(3)  │
                        │       │    timestamp            │
                        │       │    created_at           │
                        │       │    raw_payload TEXT     │
                        │       └─────────────────────────┘
                        │
                        └─── Denormalized FK for query efficiency
```

## Tables Overview

### 1. Merchants Table
Stores merchant/partner information.

| Column     | Type         | Constraints      | Description                    |
|------------|--------------|------------------|--------------------------------|
| id         | VARCHAR(50)  | PRIMARY KEY      | Unique merchant identifier     |
| name       | VARCHAR(255) | NOT NULL         | Human-readable merchant name   |
| created_at | TIMESTAMP    | NOT NULL DEFAULT | Record creation time           |
| updated_at | TIMESTAMP    | NOT NULL DEFAULT | Last modification time         |

### 2. Transactions Table
Represents payment transactions with current status.

| Column      | Type             | Constraints       | Description                     |
|-------------|------------------|-------------------|---------------------------------|
| id          | VARCHAR(50)      | PRIMARY KEY       | Transaction UUID                |
| merchant_id | VARCHAR(50)      | FK → merchants.id | Associated merchant             |
| amount      | NUMERIC(15,2)    | NOT NULL          | Transaction amount              |
| currency    | VARCHAR(3)       | NOT NULL, DEFAULT | ISO currency code (INR)         |
| status      | transactionstatus| NOT NULL          | Current status (derived)        |
| created_at  | TIMESTAMP        | NOT NULL          | When transaction was initiated  |
| updated_at  | TIMESTAMP        | NOT NULL DEFAULT  | Last status update              |

**Status Values (ENUM):**
- `initiated` - Transaction created
- `processed` - Payment completed successfully
- `failed` - Payment failed
- `settled` - Settlement completed

### 3. Events Table
Immutable event log for payment lifecycle events.

| Column         | Type          | Constraints         | Description                    |
|----------------|---------------|---------------------|--------------------------------|
| id             | VARCHAR(50)   | PRIMARY KEY         | Event UUID (idempotency key)   |
| event_type     | eventtype     | NOT NULL            | Type of event                  |
| transaction_id | VARCHAR(50)   | FK → transactions.id| Associated transaction         |
| merchant_id    | VARCHAR(50)   | FK → merchants.id   | Associated merchant            |
| amount         | NUMERIC(15,2) | NOT NULL            | Amount at time of event        |
| currency       | VARCHAR(3)    | NOT NULL, DEFAULT   | Currency at time of event      |
| timestamp      | TIMESTAMP     | NOT NULL            | When event occurred            |
| created_at     | TIMESTAMP     | NOT NULL DEFAULT    | When event was ingested        |
| raw_payload    | TEXT          | NULLABLE            | Original JSON for audit        |

**Event Types (ENUM):**
- `payment_initiated` - Transaction started
- `payment_processed` - Payment successfully processed
- `payment_failed` - Payment failed
- `settled` - Funds settled to merchant

## Indexes

### Transactions Indexes
| Index Name                        | Columns                  | Purpose                           |
|-----------------------------------|--------------------------|-----------------------------------|
| ix_transactions_merchant_id       | merchant_id              | Filter by merchant                |
| ix_transactions_status            | status                   | Filter by status                  |
| ix_transactions_created_at        | created_at               | Date range queries, sorting       |
| ix_transactions_merchant_status   | merchant_id, status      | Combined merchant + status filter |
| ix_transactions_merchant_created  | merchant_id, created_at  | Merchant transactions by date     |
| ix_transactions_status_created    | status, created_at       | Reconciliation queries            |

### Events Indexes
| Index Name                      | Columns                  | Purpose                            |
|---------------------------------|--------------------------|------------------------------------|
| ix_events_transaction_id        | transaction_id           | Fetch event history                |
| ix_events_merchant_id           | merchant_id              | Merchant event queries             |
| ix_events_event_type            | event_type               | Filter by event type               |
| ix_events_timestamp             | timestamp                | Date range queries                 |
| ix_events_transaction_timestamp | transaction_id, timestamp| Transaction event history ordered  |
| ix_events_type_timestamp        | event_type, timestamp    | Reconciliation by type and date    |

## Design Decisions

### 1. Idempotency via Primary Key
- `Event.id` is the primary key, making duplicate event submission impossible
- INSERT will fail with unique constraint violation if same event_id is submitted twice
- This is the most efficient idempotency mechanism in PostgreSQL

### 2. Denormalization Choices
- **merchant_id in events**: Avoids JOIN through transactions for merchant-level queries
- **status in transactions**: Avoids computing from events on every read
- **Tradeoff**: Slight data redundancy for significant query performance gains

### 3. Timestamp Handling
- **timestamp**: When event occurred (from source system)
- **created_at**: When record was created in our system
- Distinction important for debugging latency issues and auditing

### 4. NUMERIC vs FLOAT for Amount
- `NUMERIC(15,2)` supports amounts up to 9,999,999,999,999.99
- Exact decimal arithmetic, no floating point errors
- Essential for financial calculations

### 5. ENUM Types
- Database-level validation of status/event_type values
- More efficient storage than VARCHAR
- Self-documenting valid values

### 6. Foreign Key Constraints
- ON DELETE RESTRICT prevents orphaned records
- Ensures referential integrity at database level

## Query Patterns

### List Transactions with Filters
```sql
SELECT t.*, m.name as merchant_name
FROM transactions t
JOIN merchants m ON t.merchant_id = m.id
WHERE t.merchant_id = :merchant_id      -- Uses ix_transactions_merchant_id
  AND t.status = :status                 -- Uses ix_transactions_merchant_status
  AND t.created_at BETWEEN :start AND :end
ORDER BY t.created_at DESC
LIMIT :limit OFFSET :offset;
```

### Get Transaction with Event History
```sql
SELECT t.*, m.name as merchant_name
FROM transactions t
JOIN merchants m ON t.merchant_id = m.id
WHERE t.id = :transaction_id;

SELECT * FROM events
WHERE transaction_id = :transaction_id
ORDER BY timestamp ASC;  -- Uses ix_events_transaction_timestamp
```

### Reconciliation Summary
```sql
SELECT 
    merchant_id,
    DATE(created_at) as date,
    status,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount
FROM transactions
WHERE created_at BETWEEN :start AND :end
GROUP BY merchant_id, DATE(created_at), status
ORDER BY date DESC, merchant_id;
```

### Find Discrepancies
```sql
-- Processed but not settled
SELECT t.*
FROM transactions t
WHERE t.status = 'processed'
  AND t.updated_at < NOW() - INTERVAL '24 hours'
  AND NOT EXISTS (
      SELECT 1 FROM events e 
      WHERE e.transaction_id = t.id 
      AND e.event_type = 'settled'
  );

-- Settled after failure
SELECT t.*
FROM transactions t
JOIN events e ON e.transaction_id = t.id
WHERE t.status = 'failed'
  AND e.event_type = 'settled';
```
