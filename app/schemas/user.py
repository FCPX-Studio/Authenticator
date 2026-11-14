from pydantic import AwareDatetime, BaseModel

from typing import Optional


class User(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    marketing: bool = False
    subscribed_at: Optional[AwareDatetime] = None    # Set by the DB on first insert

class UserLicense(BaseModel):
    id: Optional[str] = None
    key: str
    product_id: str
    product_license_id: str
    order_id: str
    user_id: str
    activation_seats: int
    created_at: AwareDatetime
    expires_at: Optional[AwareDatetime] = None

class UserActivation(BaseModel):
    id: Optional[str] = None
    machine_fingerprint: str
    machine_name: str
    app_version: str
    fcpx_version: Optional[str] = None
    macos_version: Optional[str] = None
    last_activated_at: Optional[AwareDatetime] = None

class SignedActivation(BaseModel):
    payload: str
    signature_algorithm: str
    signature: bytes

class LicenseToken(BaseModel):
    activation_id: str
    activation_seats: int
    activations_used: int
    license: SignedActivation