from app.schemas.paddle import PaddleCustomer
from app.schemas.user import User, UserLicense, UserActivation
from app.schemas.product import ProductLicense

from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone


class ProductLicenseRequest(BaseModel):
    product_license_id: str     # Paddle product_id
    customer: PaddleCustomer

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
            activation_seats=product_license.activation_seats,
            created_at=now,
            expires_at=expires_at
        )

class OrderLicensesRequest(BaseModel):
    order_id: str
    items: list[ProductLicenseRequest]
    

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

    