from sqlalchemy.orm import Session, sessionmaker
from app.db.database import Database
from app.db.models.product import ProductLicenseRow

from app.schemas.product import ProductLicense

from typing import Optional

from sqlalchemy import select


class ProductRepository(Database):

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        super().__init__(session_factory)
        self.create_tables()

    # --- MAPPING

    @staticmethod
    def _to_product_license(row: ProductLicenseRow) -> ProductLicense:
        return ProductLicense(
            id=row.id,
            product_id=row.product_id,
            activation_seats=row.activation_seats,
            life_duration=row.life_duration,
        )

    # --- GET

    def get_product_license(self, product_license_id: str) -> Optional[ProductLicense]:
        """
        Retrieve a license offered on the website from its Paddle product ID

        Args:
            product_license_id (str): Paddle product ID (pro_…)

        Returns:
            Optional[ProductLicense]: Corresponding product license, None if unknown
        """
        with self.session() as s:
            row = s.get(ProductLicenseRow, product_license_id)
            return self._to_product_license(row) if row else None
