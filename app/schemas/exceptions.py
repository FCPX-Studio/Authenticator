from typing import Optional
from datetime import datetime


class InvalideLicenseKeyError(Exception):
    def __init__(self, license_key: str) -> None:
        self.license_key = license_key
        super().__init__(f"Invalide license key '{license_key}'")

class ExpiredLicenseError(Exception):
    def __init__(self, license_key: str, expiration_date: Optional[datetime]) -> None:
        self.license_key = license_key
        self.expiration_date = expiration_date
        super().__init__(f"License '{license_key}' expired on {expiration_date}")

class ActivationNotFoundError(Exception):
    def __init__(self, activation_id: str) -> None:
        self.activation_id = activation_id
        super().__init__(f"Invalide activation ID '{activation_id}'")

class ActivationLimitReachedError(Exception):
    def __init__(self, license_key: str, activation_limit: int) -> None:
        self.license_key = license_key
        self.activation_limit = activation_limit
        super().__init__(f"Activations limit reached ({activation_limit}) for license '{license_key}'")