from sqlalchemy.orm import Session, sessionmaker
from app.db.database import Database
from app.db.models.license import LicenseRow, LicenseActivationRow

from app.schemas.license import License, LicenseActivation
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
    def _to_license(row: LicenseRow) -> License:
        return License(
            id=row.id,
            key=row.license_key,
            product_id=row.product_id,
            activation_limit=row.activation_limit,
            customer_email=row.customer_email,  # type: ignore[arg-type]
            order_id=row.order_id,  # type: ignore[arg-type]
            created_at=row.created_at,
            expires_at=row.expires_at,  # type: ignore[arg-type]
        )

    @staticmethod
    def _to_activation(row: LicenseActivationRow) -> LicenseActivation:
        return LicenseActivation(
            id=row.id,
            machine_fingerprint=row.machine_fingerprint,
            machine_name=row.machine_name,  # type: ignore[arg-type]
            app_version=row.app_version,  # type: ignore[arg-type]
            fcpx_version=row.fcpx_version,
            macos_version=row.macos_version,
            created_at=row.created_at,
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
            return bool(s.scalar(select(exists().where(LicenseRow.license_key == license_key))))

    def get_license(self, license_key: str) -> Optional[License]:
        """
        Retrieve a license from its key

        Args:
            license_key (str): License key

        Returns:
            Optional[License]: Corresponding license, None if the key is unknown
        """
        with self.session() as s:
            row = s.scalar(select(LicenseRow).where(LicenseRow.license_key == license_key))
            return self._to_license(row) if row else None

    def get_license_activations(self, license_key: str) -> list[LicenseActivation]:
        """
        Retrieve activations of a license

        Args:
            license_key (str): Licence key

        Returns:
            list[LicenseActivation]: List of all activations for this license
        """
        with self.session() as s:
            rows = s.scalars(
                select(LicenseActivationRow)
                .join(LicenseActivationRow.license)
                .where(LicenseRow.license_key == license_key)
                .order_by(LicenseActivationRow.created_at)
            ).all()
            return [self._to_activation(r) for r in rows]

    # --- UPDATE

    def update_activation(
            self,
            activation_id: str,
            activation: LicenseActivation
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
                update(LicenseActivationRow)
                .where(LicenseActivationRow.id == activation_id)
                .values(
                    app_version=activation.app_version,
                    fcpx_version=activation.fcpx_version,
                    macos_version=activation.macos_version,
                    last_activated_at=func.now(),
                )
                .returning(LicenseActivationRow.id)
            )
            if updated_id is None:
                raise ActivationNotFoundError(activation_id)
            return updated_id

    # --- WRITE

    def save_license(self, license: License) -> str:
        """
        Save a license in DB

        Args:
            license (License): License to save

        Returns:
            str: Created license ID
        """
        with self.session() as s:
            row = LicenseRow(
                license_key=license.key,
                product_id=license.product_id,
                activation_limit=license.activation_limit,
                customer_email=license.customer_email,
                order_id=license.order_id,
                created_at=license.created_at,
                expires_at=license.expires_at,
            )
            if license.id:
                row.id = license.id
            s.add(row)
            s.flush()  # assigns the generated id
            return row.id

    def save_activation(self, license_key: str, activation: LicenseActivation) -> str:
        """
        Save a activation in DB
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
            license_id = s.scalar(select(LicenseRow.id).where(LicenseRow.license_key == license_key))
            if license_id is None:
                raise InvalideLicenseKeyError(license_key)

            values = dict(
                license_id=license_id,
                machine_fingerprint=activation.machine_fingerprint,
                machine_name=activation.machine_name,
                app_version=activation.app_version,
                fcpx_version=activation.fcpx_version,
                macos_version=activation.macos_version,
            )
            if activation.id:
                values["id"] = activation.id

            stmt = insert(LicenseActivationRow).values(**values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_license_activations_license_machine",
                set_=dict(
                    machine_name=stmt.excluded.machine_name,
                    app_version=stmt.excluded.app_version,
                    fcpx_version=stmt.excluded.fcpx_version,
                    macos_version=stmt.excluded.macos_version,
                    last_activated_at=func.now(),
                ),
            ).returning(LicenseActivationRow.id)

            return s.execute(stmt).scalar_one()
