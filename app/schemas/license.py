from pydantic import BaseModel

from typing import Optional
from datetime import datetime


class License(BaseModel):
    id: Optional[str] = None
    key: str
    product_id: str
    order_id: str
    item_id: str
    activation_limit: int
    customer_email: str
    created_at: datetime
    expires_at: Optional[datetime] = None

class LicenseActivation(BaseModel):
    id: Optional[str] = None
    machine_fingerprint: str
    machine_name: str
    app_version: str
    fcpx_version: Optional[str] = None
    macos_version: Optional[str] = None
    created_at: datetime
    last_activated_at: Optional[datetime] = None

class SignedActivation(BaseModel):
    payload: str
    signature_algorithm: str
    signature: bytes

class LicenseToken(BaseModel):
    activation_id: str
    activation_limit: int
    activations_used: int
    license: SignedActivation