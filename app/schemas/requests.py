from app.schemas.license import License, LicenseActivation

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ItemLicenseRequest(BaseModel):
    item_id: str
    product_id: str
    activation_limit: int
    customer_email: str
    expires_at: Optional[datetime]

    def build_license(self, key: str, order_id: str) -> License:
        return License(
            key=key,
            product_id=self.product_id,
            activation_limit=self.activation_limit,
            customer_email=self.customer_email,
            order_id=order_id,
            item_id=self.item_id,
            created_at=datetime.now(),
            expires_at=self.expires_at
        )

class OrderLicenseRequest(BaseModel):
    order_id: str
    items: list[ItemLicenseRequest]
    

class ActivateLicenseRequest(BaseModel):
    license_key: str
    product_id: str
    machine_fingerprint: str
    machine_name: str
    app_version: str
    fcpx_version: Optional[str]
    macOS_version: Optional[str]

    def build_activation(self) -> LicenseActivation:
        return LicenseActivation(
            machine_fingerprint=self.machine_fingerprint,
            machine_name=self.machine_name,
            app_version=self.app_version,
            fcpx_version=self.fcpx_version,
            macos_version=self.macOS_version,
            created_at=datetime.now(),
        )

    