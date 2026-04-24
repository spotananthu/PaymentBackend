"""Create initial schema with merchants, transactions, and events tables.

Revision ID: 001
Revises: 
Create Date: 2026-04-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create merchants table
    op.create_table(
        'merchants',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('merchant_id', sa.String(50), sa.ForeignKey('merchants.id'), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('status', sa.Enum('initiated', 'processed', 'failed', 'settled', name='transactionstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    
    # Indexes for transactions
    op.create_index('ix_transactions_merchant_id', 'transactions', ['merchant_id'])
    op.create_index('ix_transactions_status', 'transactions', ['status'])
    op.create_index('ix_transactions_created_at', 'transactions', ['created_at'])
    op.create_index('ix_transactions_merchant_status', 'transactions', ['merchant_id', 'status'])
    op.create_index('ix_transactions_merchant_created', 'transactions', ['merchant_id', 'created_at'])
    op.create_index('ix_transactions_status_created', 'transactions', ['status', 'created_at'])

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('event_type', sa.Enum('payment_initiated', 'payment_processed', 'payment_failed', 'settled', name='eventtype'), nullable=False),
        sa.Column('transaction_id', sa.String(50), sa.ForeignKey('transactions.id'), nullable=False),
        sa.Column('merchant_id', sa.String(50), sa.ForeignKey('merchants.id'), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('raw_payload', sa.Text(), nullable=True),
    )
    
    # Indexes for events
    op.create_index('ix_events_transaction_id', 'events', ['transaction_id'])
    op.create_index('ix_events_merchant_id', 'events', ['merchant_id'])
    op.create_index('ix_events_event_type', 'events', ['event_type'])
    op.create_index('ix_events_timestamp', 'events', ['timestamp'])
    op.create_index('ix_events_transaction_timestamp', 'events', ['transaction_id', 'timestamp'])
    op.create_index('ix_events_type_timestamp', 'events', ['event_type', 'timestamp'])
    
    # Create views for reconciliation reporting
    op.execute("""
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
        JOIN merchants m ON t.merchant_id = m.id
    """)


def downgrade() -> None:
    # Drop views
    op.execute('DROP VIEW IF EXISTS v_transaction_summary')
    
    op.drop_table('events')
    op.drop_table('transactions')
    op.drop_table('merchants')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS transactionstatus')
    op.execute('DROP TYPE IF EXISTS eventtype')
