"""
Payment Reconciliation Service - Main Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import events, transactions, reconciliation, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - startup and shutdown events."""
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: Cleanup if needed
    pass


def create_application() -> FastAPI:
    """Application factory pattern for creating the FastAPI app."""
    
    app = FastAPI(
        title="Payment Reconciliation Service",
        description="""
        A lightweight backend service for payment event processing and reconciliation.
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(events.router, prefix="/events", tags=["Events"])
    app.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
    app.include_router(reconciliation.router, prefix="/reconciliation", tags=["Reconciliation"])
    
    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
