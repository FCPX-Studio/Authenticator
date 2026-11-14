from config import settings

from app.schemas.requests import OrderLicensesRequest, ProductLicenseRequest, ActivateLicenseRequest
from app.schemas.user import User, UserLicense, LicenseToken
from app.schemas.exceptions import (
    InvalideLicenseKeyError,
    ExpiredLicenseError,
    ActivationLimitReachedError,
    ProductLicenseNotFoundError,
)
from app.db.repositories import LicenseRepository, ProductRepository
from app.keytool import Keytool

from typing import Optional
from datetime import datetime, timezone


class Licensing:
    """
    Manage license creation and validation
    """

    def __init__(self) -> None:
        self.repository = LicenseRepository()
        self.product_repository = ProductRepository()
        self.keytool = Keytool()

    @staticmethod
    def _now() -> datetime:
        """
        Get current datetime, timezone aware (DB dates are returned in UTC)

        Returns:
            datetime: Current datetime
        """
        return datetime.now(timezone.utc)
    
    def _bad_license(self, license: Optional[UserLicense], product_id: str) -> bool:
        """
        Validate a license, reject None and make sure product_id match

        Args:
            license (License): License to validate
            product_id: Product ID to check

        Returns:
            bool: True if bad license, else False
        """
        if not license:
            return True
        
        return license.product_id != product_id
    
    def _license_expired(self, license: UserLicense) -> bool:
        """
        Check if a license is expired

        Args:
            license (License): License to check expiration

        Returns:
            bool: True if expired, else False
        """
        if not license.expires_at:
            return False
        
        return self._now() >= license.expires_at

    def _create_item_license(
            self,
            order_id: str,
            item_request: ProductLicenseRequest,
            user: User
        ) -> UserLicense:
        """
        Build the license for a specific item (not saved in DB)
        Seats and lifetime come from the ProductLicense catalog

        Args:
            order_id (str): ID of the order
            item_request (ProductLicenseRequest): License request for a specific item
            user (User): Owner of the license

        Returns:
            UserLicense: Created license

        Raises:
            ProductLicenseNotFoundError: Unknown Paddle product ID
        """
        product_license = self.product_repository.get_product_license(item_request.product_license_id)
        if product_license is None:
            raise ProductLicenseNotFoundError(item_request.product_license_id)

        # Create a unique license key
        while True:
            key = self.keytool.generate_cuuid()
            if not self.repository.license_key_exists(key):
                break
        
        # Build license
        license = item_request.build_license(
            key, order_id, product_license, user
        )

        return license
    
    def create_licenses(
            self,
            order_request: OrderLicensesRequest
        ) -> list[str]:  
        """
        Create licenses for each items of an order

        Args:
            order_request (OrderLicenseRequest): Order license creation request

        Returns:
            list[str]: License keys, normalized UUID (XXXX-XXXX-XXXX-XXXX)

        Raises:
            ProductLicenseNotFoundError: An item references an unknown Paddle product ID,
                nothing is saved
        """
        # Prevent duplicate licenses for a single order
        order_licenses = self.repository.get_order_licenses(order_request.order_id)
        if order_licenses:
            return [lcs.key for lcs in order_licenses]

        users: dict[str, User] = {}
        licenses: list[UserLicense] = []
        for item in order_request.items:
            user = item.customer.build_user()
            users[user.id] = user
            licenses.append(
                self._create_item_license(order_request.order_id, item, user)
            )

        # Save users and licenses (single transaction) and return db keys
        unique_users = list(users.values())
        valid_keys = self.repository.save_licenses(unique_users, licenses)
        return valid_keys
    
    def activate_license(
            self,
            activation_request: ActivateLicenseRequest
        ) -> LicenseToken:
        """
        Validate informations then create a signed token.
        Check for validation
            - Product match
            - License expiration
            - Activations count

        Args:
            license_key (str): User license key
            product_id (str): Product to license
            fingerprint (str): User machine fingerprint

        Returns:
            LicenseToken: Signed license token
        """
        license_key = self.keytool.normalize_cuuid(activation_request.license_key)
        now = self._now()

        # Validate license with product and check expiration date
        license = self.repository.get_license(license_key)

        if self._bad_license(license, activation_request.product_id):
            raise InvalideLicenseKeyError(license_key)
        assert license and license.id # retrieved license should have a ID
        if self._license_expired(license):
            raise ExpiredLicenseError(license.key, license.expires_at)

        # Check for activation limit and update
        past_activations = self.repository.get_license_activations(license.key)
        fingerprint_activations = { pa.machine_fingerprint: pa for pa in past_activations }
        user_current_activation = fingerprint_activations.get(activation_request.machine_fingerprint)

        activation = activation_request.build_activation()

        if user_current_activation:
            assert user_current_activation.id # retrieved activations should have a ID
            activation_id = self.repository.update_activation(user_current_activation.id, activation)
        elif len(past_activations) < license.activation_seats:
            activation_id = self.repository.save_activation(license.key, activation)
            fingerprint_activations[activation.machine_fingerprint] = activation
        else:
            raise ActivationLimitReachedError(license.key, license.activation_seats)

        signed_activation = self.keytool.create_signed_license_activation(
            format_version=settings.LICENSE_TOKEN_FORMAT_VERSION,
            license_id=license.id,
            product_id=license.product_id,
            fingerprint=activation.machine_fingerprint,
            issued_at=now,
            expire_at=license.expires_at
        )

        return LicenseToken(
            activation_id=activation_id,
            activation_seats=license.activation_seats,
            activations_used=len(fingerprint_activations),
            license=signed_activation
        )