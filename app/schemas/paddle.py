from app.schemas.user import User

from pydantic import AwareDatetime, BaseModel
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
