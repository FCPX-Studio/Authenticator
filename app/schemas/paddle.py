from app.schemas.user import User

from pydantic import AwareDatetime, BaseModel, Field
from typing import Optional


class PaddleCustomer(BaseModel):
    """
    Paddle Billing customer entity
    Unknown fields (custom_data, import_meta…) are ignored
    """
    id: str                                 # Paddle customer ID (ctm_…)
    email: str
    name: Optional[str] = None              # Full name, single field in Paddle
    marketing_consent: bool = False
    status: Optional[str] = None            # "active" | "archived"
    locale: Optional[str] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

    def build_user(self) -> User:
        """
        Build User instance
        subscribed_at is left empty: the DB sets it when the customer is first inserted
        """
        name = self.name.strip() if self.name else None

        return User(
            id=self.id,
            email=self.email,
            name=name or None,
            marketing=self.marketing_consent,
        )


# --- WEBHOOK: transaction.completed
# Only the fields used for licensing are modeled, unknown fields are ignored

class PaddlePrice(BaseModel):
    """Price of a transaction item"""
    id: str                                 # Paddle price ID (pri_…)
    product_id: str                         # Paddle product ID (pro_…), matches ProductLicense.id


class PaddleTransactionItem(BaseModel):
    """Item of a transaction"""
    price: PaddlePrice
    quantity: int = Field(default=1, ge=1)


class PaddleTransaction(BaseModel):
    """Paddle Billing transaction entity (webhook `data`)"""
    id: str                                 # Paddle transaction ID (txn_…), used as order ID
    status: str                             # "completed" for transaction.completed
    customer_id: str                        # Paddle customer ID (ctm_…), details fetched via API
    items: list[PaddleTransactionItem]
