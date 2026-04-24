"""
Merchant Repository - Data access layer for merchants.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.entities import Merchant


class MerchantRepository:
    """Repository for Merchant data access."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, merchant_id: str) -> Optional[Merchant]:
        """Get merchant by ID."""
        return self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
    
    def exists(self, merchant_id: str) -> bool:
        """Check if merchant exists."""
        return self.db.query(
            self.db.query(Merchant).filter(Merchant.id == merchant_id).exists()
        ).scalar()
    
    def create(self, merchant: Merchant) -> Merchant:
        """Create a new merchant."""
        self.db.add(merchant)
        self.db.flush()
        return merchant
    
    def get_or_create(self, merchant_id: str, merchant_name: str) -> Merchant:
        """Get existing merchant or create if doesn't exist."""
        merchant = self.get_by_id(merchant_id)
        if not merchant:
            merchant = Merchant(id=merchant_id, name=merchant_name)
            try:
                self.db.add(merchant)
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                merchant = self.get_by_id(merchant_id)
        return merchant
    
    def list_all(self) -> List[Merchant]:
        """Get all merchants."""
        return self.db.query(Merchant).order_by(Merchant.name).all()
    
    def update_name(self, merchant_id: str, new_name: str) -> Optional[Merchant]:
        """Update merchant name."""
        merchant = self.get_by_id(merchant_id)
        if merchant:
            merchant.name = new_name
            self.db.flush()
        return merchant
