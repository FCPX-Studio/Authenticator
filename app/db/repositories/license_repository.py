from sqlalchemy.orm import Session, joinedload, sessionmaker
from app.db.database import Database
from app.db.models.users import UserRow, UserLicenseRow, UserActivationRow, UserMachineRow

from app.schemas.user import User, UserLicense, UserActivation
from app.schemas.exceptions import InvalideLicenseKeyError, ActivationNotFoundError

from typing import Optional

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert


class LicenseRepository(Database):

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        super().__init__(session_factory)
        self.create_tables()

    # --- MAPPING

    @staticmethod
    def _to_license(row: UserLicenseRow) -> UserLicense:
        return UserLicense(
            id=row.id,
            key=row.license_key,
            product_id=row.product_id,
            product_license_id=row.product_license_id,
            order_id=row.order_id,
            user_id=row.user_id,
            activation_seats=row.activation_seats,
            created_at=row.created_at,
            expires_at=row.expires_at,  # type: ignore[arg-type]
        )

    @staticmethod
    def _to_activation(row: UserActivationRow) -> UserActivation:
        # Machine must be loaded (joinedload) or the row still attached to a session
        return UserActivation(
            id=row.id,
            machine_fingerprint=row.machine.machine_fingerprint,
            machine_name=row.machine.machine_name,  # type: ignore[arg-type]
            app_version=row.app_version,  # type: ignore[arg-type]
            fcpx_version=row.fcpx_version,
            macos_version=row.macos_version,
            last_activated_at=row.last_activated_at,
        )

    # --- GET

    def license_key_exists(self, license_key: str) -> bool:
        """
        Check if a license key exists

        Args:
            license_key (str): License key to check

        Returns:
            bool: Exists in DB
        """
        with self.session() as s:
            return bool(s.scalar(select(exists().where(UserLicenseRow.license_key == license_key))))

    def get_license(self, license_key: str) -> Optional[UserLicense]:
        """
        Retrieve a license from its key

        Args:
            license_key (str): License key

        Returns:
            Optional[License]: Corresponding license, None if the key is unknown
        """
        with self.session() as s:
            row = s.scalar(select(UserLicenseRow).where(UserLicenseRow.license_key == license_key))
            return self._to_license(row) if row else None

    def get_order_licenses(self, order_id: str) -> Optional[list[UserLicense]]:
        """
        Retrieve every license created for an order

        Args:
            order_id (str): Order ID

        Returns:
            Optional[list[License]]: Licenses of the order, None if the order has no license
        """
        with self.session() as s:
            rows = s.scalars(
                select(UserLicenseRow)
                .where(UserLicenseRow.order_id == order_id)
                .order_by(UserLicenseRow.created_at, UserLicenseRow.id)
            ).all()
            return [self._to_license(r) for r in rows] or None

    def get_license_activations(self, license_key: str) -> list[UserActivation]:
        """
        Retrieve activations of a license

        Args:
            license_key (str): Licence key

        Returns:
            list[LicenseActivation]: List of all activations for this license
        """
        with self.session() as s:
            rows = s.scalars(
                select(UserActivationRow)
                .join(UserActivationRow.license)
                .options(joinedload(UserActivationRow.machine))
                .where(UserLicenseRow.license_key == license_key)
                .order_by(UserActivationRow.last_activated_at)
            ).all()
            return [self._to_activation(r) for r in rows]

    # --- UPDATE

    def update_activation(
            self,
            activation_id: str,
            activation: UserActivation
        ) -> str:
        """
        Update informations for a specific activation
        Only app_version, fcpx_version, macos_version and last_activated_at are updated

        Args:
            activation_id (str): ID of the activation to update
            activation (LicenseActivation): New activation content

        Returns:
            str: Updated activation ID (same as activation_id)

        Raises:
            InvalideActivationID: No activation with this ID
        """
        with self.session() as s:
            updated_id = s.scalar(
                update(UserActivationRow)
                .where(UserActivationRow.id == activation_id)
                .values(
                    app_version=activation.app_version,
                    fcpx_version=activation.fcpx_version,
                    macos_version=activation.macos_version,
                    last_activated_at=func.now(),
                )
                .returning(UserActivationRow.id)
            )
            if updated_id is None:
                raise ActivationNotFoundError(activation_id)
            return updated_id

    # --- WRITE

    def save_licenses(self, users: list[User], licenses: list[UserLicense]) -> list[str]:
        """
        Save the license owners then their licenses, in a single transaction (all or nothing)
        An existing user is updated (email, name, marketing), subscribed_at is kept
        If a license already exists for the same order and product license, it is left
        untouched and the key of the existing license is returned instead

        Args:
            users (list[User]): Owners of the licenses, written before the licenses (FK)
            licenses (list[UserLicense]): Licenses to save

        Returns:
            list[str]: Stored license keys, in the same order as `licenses`

        Raises:
            IntegrityError: Any other constraint violation (e.g. license key collision,
                email already used by another user), the whole transaction is rolled back
        """
        keys: list[str] = []

        with self.session() as s:
            for user in users:
                # subscribed_at is never sent: set by the DB on first insert, kept on update
                stmt = insert(UserRow).values(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    marketing=user.marketing,
                )
                s.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[UserRow.id],
                        set_=dict(
                            email=stmt.excluded.email,
                            name=stmt.excluded.name,
                            marketing=stmt.excluded.marketing,
                        ),
                    )
                )

            for license in licenses:
                values = dict(
                    license_key=license.key,
                    product_license_id=license.product_license_id,
                    order_id=license.order_id,
                    user_id=license.user_id,
                    product_id=license.product_id,
                    activation_seats=license.activation_seats,
                    created_at=license.created_at,
                    expires_at=license.expires_at,
                )
                if license.id:
                    values["id"] = license.id

                inserted_key = s.scalar(
                    insert(UserLicenseRow)
                    .values(**values)
                    .on_conflict_do_nothing(constraint="uq_UserLicense_order_product_license")
                    .returning(UserLicenseRow.license_key)
                )

                if inserted_key is None:
                    # Already exists: keep the original license and return its key
                    inserted_key = s.scalar(
                        select(UserLicenseRow.license_key).where(
                            UserLicenseRow.order_id == license.order_id,
                            UserLicenseRow.product_license_id == license.product_license_id,
                        )
                    )
                    assert inserted_key is not None  # conflict guarantees the row exists

                keys.append(inserted_key)

        return keys

    def save_activation(self, license_key: str, activation: UserActivation) -> str:
        """
        Save a activation in DB, in a single transaction
        The machine is created from its fingerprint, or its name refreshed if already known
        (a machine is shared by every license activated on it)
        If this machine is already activated on the license, the existing row is
        refreshed instead (one seat per machine, safe against concurrent requests)

        Args:
            license_key (str): Key of the license been activated
            activation (LicenseActivation): Activation informations

        Returns:
            str: Activation ID

        Raises:
            InvalideLicenseKeyError: Unknown license key
        """
        with self.session() as s:
            license_id = s.scalar(select(UserLicenseRow.id).where(UserLicenseRow.license_key == license_key))
            if license_id is None:
                raise InvalideLicenseKeyError(license_key)

            # Upsert the machine on its fingerprint and get its ID back
            machine_stmt = insert(UserMachineRow).values(
                machine_fingerprint=activation.machine_fingerprint,
                machine_name=activation.machine_name,
            )
            machine_id = s.execute(
                machine_stmt.on_conflict_do_update(
                    index_elements=[UserMachineRow.machine_fingerprint],
                    set_=dict(machine_name=machine_stmt.excluded.machine_name),
                ).returning(UserMachineRow.id)
            ).scalar_one()

            values = dict(
                license_id=license_id,
                machine_id=machine_id,
                app_version=activation.app_version,
                fcpx_version=activation.fcpx_version,
                macos_version=activation.macos_version,
            )
            if activation.id:
                values["id"] = activation.id

            stmt = insert(UserActivationRow).values(**values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_UserActivation_license_machine",
                set_=dict(
                    app_version=stmt.excluded.app_version,
                    fcpx_version=stmt.excluded.fcpx_version,
                    macos_version=stmt.excluded.macos_version,
                    last_activated_at=func.now(),
                ),
            ).returning(UserActivationRow.id)

            return s.execute(stmt).scalar_one()
