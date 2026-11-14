from pydantic import BaseModel

from typing import Optional
from datetime import timedelta


class ProductLicense(BaseModel):
    id: str
    product_id: str
    activation_seats: int
    life_duration: Optional[timedelta] = None
