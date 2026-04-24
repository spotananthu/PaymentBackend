"""
Reconciliation Repository - Data access for reconciliation queries.
Uses raw SQL for complex aggregations and discrepancy detection.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.entities import Transaction, Event, EventType, TransactionStatus


class ReconciliationRepository:
    """Repository for reconciliation-related queries."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_summary_by_merchant(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get reconciliation summary grouped by merchant."""
        
        sql = """
        SELECT 
            t.merchant_id,
            m.name as merchant_name,
            COUNT(*) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount,
            COUNT(CASE WHEN t.status = 'settled' THEN 1 END) as settled_count,
            COALESCE(SUM(CASE WHEN t.status = 'settled' THEN t.amount END), 0) as settled_amount,
            COUNT(CASE WHEN t.status = 'processed' THEN 1 END) as processed_count,
            COALESCE(SUM(CASE WHEN t.status = 'processed' THEN t.amount END), 0) as processed_amount,
            COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_count,
            COALESCE(SUM(CASE WHEN t.status = 'failed' THEN t.amount END), 0) as failed_amount,
            COUNT(CASE WHEN t.status = 'initiated' THEN 1 END) as initiated_count,
            COALESCE(SUM(CASE WHEN t.status = 'initiated' THEN t.amount END), 0) as initiated_amount
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        WHERE 1=1
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " GROUP BY t.merchant_id, m.name ORDER BY total_amount DESC"
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def get_summary_by_date(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get reconciliation summary grouped by date."""
        
        sql = """
        SELECT 
            DATE(t.created_at) as date,
            COUNT(*) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount,
            COUNT(CASE WHEN t.status = 'settled' THEN 1 END) as settled_count,
            COALESCE(SUM(CASE WHEN t.status = 'settled' THEN t.amount END), 0) as settled_amount,
            COUNT(CASE WHEN t.status = 'processed' THEN 1 END) as processed_count,
            COALESCE(SUM(CASE WHEN t.status = 'processed' THEN t.amount END), 0) as processed_amount,
            COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_count,
            COALESCE(SUM(CASE WHEN t.status = 'failed' THEN t.amount END), 0) as failed_amount,
            COUNT(CASE WHEN t.status = 'initiated' THEN 1 END) as initiated_count,
            COALESCE(SUM(CASE WHEN t.status = 'initiated' THEN t.amount END), 0) as initiated_amount
        FROM transactions t
        WHERE 1=1
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " GROUP BY DATE(t.created_at) ORDER BY date DESC"
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def get_summary_by_status(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get reconciliation summary grouped by status."""
        
        sql = """
        SELECT 
            t.status,
            COUNT(*) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount
        FROM transactions t
        WHERE 1=1
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " GROUP BY t.status ORDER BY total_transactions DESC"
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def get_summary_by_merchant_status(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get reconciliation summary grouped by merchant AND status.
        
        This provides a detailed breakdown showing the count of transactions
        for each status within each merchant, using SQL GROUP BY for efficiency.
        
        Returns:
            List of dicts with merchant_id, merchant_name, status, 
            transaction_count, and total_amount
        """
        sql = """
        SELECT 
            t.merchant_id,
            m.name as merchant_name,
            t.status,
            COUNT(*) as transaction_count,
            COALESCE(SUM(t.amount), 0) as total_amount
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        WHERE 1=1
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += """
        GROUP BY t.merchant_id, m.name, t.status
        ORDER BY t.merchant_id, t.status
        """
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def find_processed_not_settled(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        hours_threshold: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Find transactions that were processed but never settled.
        
        Uses efficient SQL query:
        - Filters transactions in 'processed' status
        - Checks if updated_at is older than threshold
        - Uses NOT EXISTS for efficiency (stops at first match)
        
        Args:
            hours_threshold: Hours after which a processed transaction 
                           should have been settled (default: 24)
        """
        sql = f"""
        SELECT 
            t.id as transaction_id,
            t.merchant_id,
            m.name as merchant_name,
            t.amount,
            t.currency,
            t.status as current_status,
            t.created_at,
            t.updated_at,
            'processed_not_settled' as discrepancy_type,
            'Payment processed but not settled within {hours_threshold} hours' as discrepancy_reason
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        WHERE t.status = 'processed'
          AND t.updated_at < (CURRENT_TIMESTAMP - INTERVAL '{hours_threshold} hours')
          AND NOT EXISTS (
              SELECT 1 FROM events e 
              WHERE e.transaction_id = t.id 
              AND e.event_type = 'settled'
          )
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " ORDER BY t.updated_at ASC"  # Oldest first (most urgent)
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def find_settled_after_failure(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find transactions where settlement occurred after a failure event.
        
        Uses efficient SQL with JOINs:
        - JOINs events table twice (for failed and settled events)
        - Compares timestamps to find settlement after failure
        - DISTINCT to handle multiple events
        
        This is a data integrity issue - a failed transaction should not 
        have a subsequent settlement.
        """
        sql = """
        SELECT DISTINCT
            t.id as transaction_id,
            t.merchant_id,
            m.name as merchant_name,
            t.amount,
            t.currency,
            t.status as current_status,
            t.created_at,
            e_fail.timestamp as failed_at,
            e_settle.timestamp as settled_at,
            'settled_after_failure' as discrepancy_type,
            'Settlement event recorded after payment failure' as discrepancy_reason
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        JOIN events e_fail ON t.id = e_fail.transaction_id 
            AND e_fail.event_type = 'payment_failed'
        JOIN events e_settle ON t.id = e_settle.transaction_id 
            AND e_settle.event_type = 'settled'
        WHERE e_settle.timestamp > e_fail.timestamp
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " ORDER BY t.created_at DESC"
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def find_duplicate_settlements(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find transactions with multiple settlement events.
        
        Uses SQL GROUP BY with HAVING for efficient counting:
        - JOINs only settled events
        - Groups by transaction
        - Filters with HAVING COUNT > 1
        
        This indicates idempotency failure or duplicate processing.
        """
        sql = """
        SELECT 
            t.id as transaction_id,
            t.merchant_id,
            m.name as merchant_name,
            t.amount,
            t.currency,
            t.status as current_status,
            t.created_at,
            COUNT(e.id) as settlement_count,
            'duplicate_settlement' as discrepancy_type,
            'Multiple settlement events recorded (' || COUNT(e.id)::text || ' settlements)' as discrepancy_reason
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        JOIN events e ON t.id = e.transaction_id AND e.event_type = 'settled'
        WHERE 1=1
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += """
        GROUP BY t.id, t.merchant_id, m.name, t.amount, t.currency, t.status, t.created_at
        HAVING COUNT(e.id) > 1
        ORDER BY COUNT(e.id) DESC, t.created_at DESC
        """
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def find_missing_initiation(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find transactions without a payment_initiated event.
        
        Uses efficient NOT EXISTS subquery:
        - Stops searching at first match (more efficient than LEFT JOIN + IS NULL)
        - Only returns transactions that have other events but no initiation
        
        This indicates data integrity issues - all transactions should 
        start with a payment_initiated event.
        """
        sql = """
        SELECT 
            t.id as transaction_id,
            t.merchant_id,
            m.name as merchant_name,
            t.amount,
            t.currency,
            t.status as current_status,
            t.created_at,
            'missing_initiation' as discrepancy_type,
            'Transaction has no payment_initiated event' as discrepancy_reason
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        WHERE NOT EXISTS (
            SELECT 1 FROM events e 
            WHERE e.transaction_id = t.id 
            AND e.event_type = 'payment_initiated'
        )
        AND EXISTS (
            SELECT 1 FROM events e2
            WHERE e2.transaction_id = t.id
        )
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " ORDER BY t.created_at DESC"
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def find_conflicting_events(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find transactions with conflicting events (both settled AND failed).
        
        Uses efficient EXISTS subqueries:
        - Checks for existence of both settlement and failure events
        - A transaction should be in one terminal state, not both
        
        This indicates serious data integrity issues - a transaction 
        cannot be both settled and failed.
        """
        sql = """
        SELECT 
            t.id as transaction_id,
            t.merchant_id,
            m.name as merchant_name,
            t.amount,
            t.currency,
            t.status as current_status,
            t.created_at,
            'conflicting_events' as discrepancy_type,
            'Transaction has both settlement and failure events' as discrepancy_reason
        FROM transactions t
        JOIN merchants m ON t.merchant_id = m.id
        WHERE EXISTS (
            SELECT 1 FROM events e_settled 
            WHERE e_settled.transaction_id = t.id 
            AND e_settled.event_type = 'settled'
        )
        AND EXISTS (
            SELECT 1 FROM events e_failed 
            WHERE e_failed.transaction_id = t.id 
            AND e_failed.event_type = 'payment_failed'
        )
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        sql += " ORDER BY t.created_at DESC"
        
        result = self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result]
    
    def get_totals(
        self,
        merchant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get aggregate totals for reconciliation summary."""
        
        sql = """
        SELECT 
            COUNT(*) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount,
            COUNT(CASE WHEN t.status = 'settled' THEN 1 END) as settled_count,
            COALESCE(SUM(CASE WHEN t.status = 'settled' THEN t.amount END), 0) as settled_amount,
            COUNT(CASE WHEN t.status = 'processed' THEN 1 END) as processed_count,
            COALESCE(SUM(CASE WHEN t.status = 'processed' THEN t.amount END), 0) as processed_amount,
            COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_count,
            COALESCE(SUM(CASE WHEN t.status = 'failed' THEN t.amount END), 0) as failed_amount,
            COUNT(CASE WHEN t.status = 'initiated' THEN 1 END) as initiated_count,
            COALESCE(SUM(CASE WHEN t.status = 'initiated' THEN t.amount END), 0) as initiated_amount
        FROM transactions t
        WHERE 1=1
        """
        
        params = {}
        
        if merchant_id:
            sql += " AND t.merchant_id = :merchant_id"
            params["merchant_id"] = merchant_id
        
        if start_date:
            sql += " AND t.created_at >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND t.created_at <= :end_date"
            params["end_date"] = end_date
        
        result = self.db.execute(text(sql), params)
        row = result.fetchone()
        return dict(row._mapping) if row else {}
