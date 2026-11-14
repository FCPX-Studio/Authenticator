from app.schemas.paddle import PaddleCustomer, PaddleTransaction
from app.schemas.user import User, UserLicense, UserActivation
from app.schemas.product import ProductLicense

from pydantic import BaseModel, AwareDatetime, Field
from typing import Optional, Literal
from datetime import datetime, timezone


class ProductLicenseRequest(BaseModel):
    product_license_id: str     # Paddle product_id
    customer: PaddleCustomer
    quantity: int = Field(default=1, ge=1)  # Multiplies the catalog activation seats

    def build_license(
            self, 
            key: str, 
            order_id: str,
            product_license: ProductLicense,
            user: User
        ) -> UserLicense:
        """Build UserLicense instance"""
        now = datetime.now(timezone.utc)
        expires_at = None
        if product_license.life_duration:
            expires_at = now + product_license.life_duration

        return UserLicense(
            key=key,
            product_id=product_license.product_id,
            product_license_id=product_license.id,
            order_id=order_id,
            user_id=user.id,
            activation_seats=product_license.activation_seats * self.quantity,
            created_at=now,
            expires_at=expires_at
        )

class OrderLicensesRequest(BaseModel):
    order_id: str
    items: list[ProductLicenseRequest]

class PaddleTransactionCompletedEvent(BaseModel):
    """
    Paddle Billing `transaction.completed` webhook notification
    https://developer.paddle.com/webhooks/transactions/transaction-completed
    """
    event_id: str                           # Paddle event ID (evt_…)
    event_type: Literal["transaction.completed"]
    occurred_at: AwareDatetime
    notification_id: Optional[str] = None   # Paddle notification ID (ntf_…)
    data: PaddleTransaction

    def build_order_request(self, customer: PaddleCustomer) -> OrderLicensesRequest:
        """
        Build OrderLicensesRequest instance, one license request per item

        Args:
            customer (PaddleCustomer): Transaction customer, fetched from Paddle API

        Returns:
            OrderLicensesRequest: Order license creation request
        """
        return OrderLicensesRequest(
            order_id=self.data.id,
            items=[
                ProductLicenseRequest(
                    product_license_id=item.price.product_id,
                    quantity=item.quantity,
                    customer=customer,
                )
                for item in self.data.items
            ],
        )
    

class ActivateLicenseRequest(BaseModel):
    license_key: str
    product_id: str
    machine_fingerprint: str
    machine_name: str
    app_version: str
    fcpx_version: Optional[str]
    macOS_version: Optional[str]

    def build_activation(self) -> UserActivation:
        """Build UserActivation instance"""
        return UserActivation(
            machine_fingerprint=self.machine_fingerprint,
            machine_name=self.machine_name,
            app_version=self.app_version,
            fcpx_version=self.fcpx_version,
            macos_version=self.macOS_version,
        )

    