"""
Pytest configuration and fixtures.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db


# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override."""
    from app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Patch the engine used in the lifespan so it uses the test SQLite engine
    with patch("app.main.engine", engine):
        with TestClient(app) as test_client:
            yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_event():
    """Sample event data for testing."""
    return {
        "event_id": "test-event-001",
        "event_type": "payment_initiated",
        "transaction_id": "test-txn-001",
        "merchant_id": "test-merchant-001",
        "merchant_name": "Test Merchant",
        "amount": 1000.50,
        "currency": "INR",
        "timestamp": "2026-01-15T10:30:00.000000+00:00"
    }


@pytest.fixture
def sample_events_flow():
    """Complete transaction flow events."""
    return [
        {
            "event_id": "flow-event-001",
            "event_type": "payment_initiated",
            "transaction_id": "flow-txn-001",
            "merchant_id": "test-merchant-001",
            "merchant_name": "Test Merchant",
            "amount": 5000.00,
            "currency": "INR",
            "timestamp": "2026-01-15T10:00:00.000000+00:00"
        },
        {
            "event_id": "flow-event-002",
            "event_type": "payment_processed",
            "transaction_id": "flow-txn-001",
            "merchant_id": "test-merchant-001",
            "merchant_name": "Test Merchant",
            "amount": 5000.00,
            "currency": "INR",
            "timestamp": "2026-01-15T10:05:00.000000+00:00"
        },
        {
            "event_id": "flow-event-003",
            "event_type": "settled",
            "transaction_id": "flow-txn-001",
            "merchant_id": "test-merchant-001",
            "merchant_name": "Test Merchant",
            "amount": 5000.00,
            "currency": "INR",
            "timestamp": "2026-01-15T12:00:00.000000+00:00"
        },
    ]
