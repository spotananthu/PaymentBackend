-- ============================================================================
-- Payment Event Processing System - PostgreSQL Schema
-- ============================================================================
-- Version: 1.0
-- Description: Schema for payment event ingestion, transaction tracking,
--              and reconciliation reporting
-- ============================================================================

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

-- Event types representing the payment lifecycle
CREATE TYPE eventtype AS ENUM (
    'payment_initiated',    -- Transaction started
    'payment_processed',    -- Payment successfully processed
    'payment_failed',       -- Payment failed
    'settled'              -- Funds settled to merchant
);

-- Transaction status derived from events
CREATE TYPE transactionstatus AS ENUM (
    'initiated',    -- Transaction created, awaiting processing
    'processed',    -- Payment completed successfully
    'failed',       -- Payment failed
    'settled'       -- Settlement completed
);

-- ============================================================================
-- TABLE: merchants
-- ============================================================================
-- Stores merchant/partner information
-- Design Decision: Separate merchants table for normalization and to store
-- merchant-specific attributes that may expand over time

CREATE TABLE merchants (
    id VARCHAR(50) PRIMARY KEY,                    -- Merchant identifier (e.g., 'merchant_1')
    name VARCHAR(255) NOT NULL,                    -- Human-readable merchant name
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),   -- Record creation timestamp
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()    -- Last update timestamp
);

COMMENT ON TABLE merchants IS 'Stores merchant/partner information';
COMMENT ON COLUMN merchants.id IS 'Unique merchant identifier';
COMMENT ON COLUMN merchants.name IS 'Human-readable merchant display name';

-- ============================================================================
-- TABLE: transactions
-- ============================================================================
-- Represents payment transactions with current status
-- Design Decision: 
-- - Status is denormalized here for query efficiency (avoids JOIN to get latest event)
-- - Amount stored here as the authoritative transaction amount
-- - Status updated when new events arrive

CREATE TABLE transactions (
    id VARCHAR(50) PRIMARY KEY,                    -- Transaction UUID
    merchant_id VARCHAR(50) NOT NULL,              -- FK to merchants
    amount NUMERIC(15, 2) NOT NULL,                -- Transaction amount (2 decimal places)
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',    -- ISO currency code
    status transactionstatus NOT NULL DEFAULT 'initiated',  -- Current transaction status
    created_at TIMESTAMP NOT NULL,                 -- When transaction was initiated
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),   -- Last status update time
    
    CONSTRAINT fk_transactions_merchant 
        FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE RESTRICT
);

COMMENT ON TABLE transactions IS 'Payment transactions with current status';
COMMENT ON COLUMN transactions.status IS 'Current status derived from latest event';
COMMENT ON COLUMN transactions.amount IS 'Transaction amount in the specified currency';

-- ============================================================================
-- TABLE: events
-- ============================================================================
-- Immutable event log storing all payment lifecycle events
-- Design Decisions:
-- - Primary key on id (event_id) ensures idempotency - duplicate events rejected
-- - Stores raw_payload for debugging and audit purposes
-- - timestamp is event occurrence time, created_at is ingestion time
-- - Denormalized merchant_id for query efficiency

CREATE TABLE events (
    id VARCHAR(50) PRIMARY KEY,                    -- Event UUID (ensures idempotency)
    event_type eventtype NOT NULL,                 -- Type of event
    transaction_id VARCHAR(50) NOT NULL,           -- FK to transactions
    merchant_id VARCHAR(50) NOT NULL,              -- FK to merchants (denormalized)
    amount NUMERIC(15, 2) NOT NULL,                -- Amount at time of event
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',    -- Currency at time of event
    timestamp TIMESTAMP NOT NULL,                  -- When event occurred
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),   -- When event was ingested
    raw_payload TEXT,                              -- Original JSON payload for audit
    
    CONSTRAINT fk_events_transaction 
        FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE RESTRICT,
    CONSTRAINT fk_events_merchant 
        FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE RESTRICT
);

COMMENT ON TABLE events IS 'Immutable event log for payment lifecycle events';
COMMENT ON COLUMN events.id IS 'Unique event ID - ensures idempotent ingestion';
COMMENT ON COLUMN events.timestamp IS 'When the event occurred in source system';
COMMENT ON COLUMN events.created_at IS 'When the event was ingested into this system';
COMMENT ON COLUMN events.raw_payload IS 'Original JSON payload for debugging/audit';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Transactions indexes
-- For filtering by merchant (GET /transactions?merchant_id=X)
CREATE INDEX ix_transactions_merchant_id ON transactions(merchant_id);

-- For filtering by status (GET /transactions?status=X)
CREATE INDEX ix_transactions_status ON transactions(status);

-- For date range filtering and sorting (GET /transactions?start_date=X&end_date=Y)
CREATE INDEX ix_transactions_created_at ON transactions(created_at);

-- Composite index for common query pattern: merchant + status filter
CREATE INDEX ix_transactions_merchant_status ON transactions(merchant_id, status);

-- Composite index for merchant + date range queries
CREATE INDEX ix_transactions_merchant_created ON transactions(merchant_id, created_at);

-- For reconciliation: find unreconciled transactions efficiently
CREATE INDEX ix_transactions_status_created ON transactions(status, created_at);

-- Events indexes
-- For fetching event history for a transaction
CREATE INDEX ix_events_transaction_id ON events(transaction_id);

-- For filtering events by merchant
CREATE INDEX ix_events_merchant_id ON events(merchant_id);

-- For filtering by event type
CREATE INDEX ix_events_event_type ON events(event_type);

-- For date range queries on events
CREATE INDEX ix_events_timestamp ON events(timestamp);

-- Composite index for transaction event history ordered by time
CREATE INDEX ix_events_transaction_timestamp ON events(transaction_id, timestamp);

-- For reconciliation queries: find events by type and date
CREATE INDEX ix_events_type_timestamp ON events(event_type, timestamp);

-- ============================================================================
-- USEFUL VIEWS (Optional - for reporting)
-- ============================================================================

-- View: Transaction summary with latest event info
CREATE OR REPLACE VIEW v_transaction_summary AS
SELECT 
    t.id AS transaction_id,
    t.merchant_id,
    m.name AS merchant_name,
    t.amount,
    t.currency,
    t.status,
    t.created_at,
    t.updated_at,
    (SELECT COUNT(*) FROM events e WHERE e.transaction_id = t.id) AS event_count,
    (SELECT MAX(timestamp) FROM events e WHERE e.transaction_id = t.id) AS last_event_at
FROM transactions t
JOIN merchants m ON t.merchant_id = m.id;

-- View: Reconciliation discrepancies
-- Identifies transactions with inconsistent states
CREATE OR REPLACE VIEW v_reconciliation_discrepancies AS
SELECT 
    t.id AS transaction_id,
    t.merchant_id,
    m.name AS merchant_name,
    t.amount,
    t.status AS current_status,
    t.created_at,
    CASE 
        -- Processed but never settled (older than 24 hours)
        WHEN t.status = 'processed' 
             AND t.updated_at < NOW() - INTERVAL '24 hours'
             AND NOT EXISTS (
                 SELECT 1 FROM events e 
                 WHERE e.transaction_id = t.id AND e.event_type = 'settled'
             )
        THEN 'processed_not_settled'
        
        -- Settled event exists for a failed transaction
        WHEN t.status = 'failed' 
             AND EXISTS (
                 SELECT 1 FROM events e 
                 WHERE e.transaction_id = t.id AND e.event_type = 'settled'
             )
        THEN 'settled_after_failure'
        
        -- Multiple conflicting status events
        WHEN (
            SELECT COUNT(DISTINCT event_type) 
            FROM events e 
            WHERE e.transaction_id = t.id 
            AND e.event_type IN ('payment_processed', 'payment_failed')
        ) > 1
        THEN 'conflicting_status'
        
        -- Duplicate events with different amounts
        WHEN EXISTS (
            SELECT 1 FROM events e1
            JOIN events e2 ON e1.transaction_id = e2.transaction_id
            WHERE e1.transaction_id = t.id
            AND e1.id < e2.id
            AND e1.event_type = e2.event_type
            AND e1.amount != e2.amount
        )
        THEN 'amount_mismatch'
        
        ELSE NULL
    END AS discrepancy_type
FROM transactions t
JOIN merchants m ON t.merchant_id = m.id
WHERE t.status != 'settled' OR EXISTS (
    SELECT 1 FROM events e 
    WHERE e.transaction_id = t.id 
    AND e.event_type = 'settled'
    AND t.status = 'failed'
);

-- ============================================================================
-- DESIGN DECISIONS & RATIONALE
-- ============================================================================

/*
1. IDEMPOTENCY VIA PRIMARY KEY
   - Event.id is the primary key, making duplicate event submission impossible
   - INSERT will fail with unique violation if same event_id is submitted twice
   - This is the most efficient idempotency mechanism in PostgreSQL

2. DENORMALIZATION CHOICES
   - merchant_id in events: Avoids JOIN through transactions for merchant-level queries
   - status in transactions: Avoids computing from events on every read
   - Tradeoff: Slight data redundancy for significant query performance gains

3. TIMESTAMP HANDLING
   - timestamp: When event occurred (from source system)
   - created_at: When record was created in our system
   - Distinction important for debugging latency issues and auditing

4. INDEX STRATEGY
   - Single-column indexes for common filter conditions
   - Composite indexes for frequent query patterns
   - Covering indexes avoided to reduce storage overhead
   - Indexes chosen based on expected API query patterns:
     * GET /transactions with filters
     * GET /reconciliation/summary grouped by merchant/date/status
     * GET /reconciliation/discrepancies

5. FOREIGN KEY CONSTRAINTS
   - ON DELETE RESTRICT prevents orphaned records
   - Ensures referential integrity at database level
   - Application should handle merchant/transaction lifecycle

6. ENUM TYPES
   - Database-level validation of status/event_type values
   - More efficient storage than VARCHAR
   - Provides documentation of valid values

7. NUMERIC vs DECIMAL for AMOUNT
   - NUMERIC(15,2) supports amounts up to 9,999,999,999,999.99
   - Exact decimal arithmetic, no floating point errors
   - Suitable for financial calculations

8. RAW_PAYLOAD STORAGE
   - Stores original JSON for audit/debugging
   - TEXT type for flexibility
   - Can be NULL to save space if not needed
*/
