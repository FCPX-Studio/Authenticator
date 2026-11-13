from app.db.models.base import Base

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

import uuid
from datetime import datetime



def _prefixed_id(prefix: str):
    """Identifiants opaques et lisibles : lic_3f2a…, act_9b5c…"""
    return lambda: f"{prefix}_{uuid.uuid4().hex}"


class LicenseRow(Base):
    __tablename__ = "licenses"
    __table_args__ = (
        CheckConstraint("activation_limit >= 0", name="ck_licenses_activation_limit"),
        # Une licence par ligne de commande : un retry du webhook ne crée pas de doublon.
        UniqueConstraint("order_id", "item_id", name="uq_licenses_order_item"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("lic"))
    # Secret : stockée en majuscules (format XXXX-XXXX-XXXX-XXXX), jamais placée dans le jeton.
    license_key: Mapped[str] = mapped_column(String(64), unique=True)
    product_id: Mapped[str] = mapped_column(String(255), index=True)
    activation_limit: Mapped[int] = mapped_column(default=2)
    # NULL = licence perpétuelle ; une date = essai (recopiée dans expiresAt du jeton).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Informations d'achat, pour le support.
    customer_email: Mapped[str | None] = mapped_column(String(320))
    order_id: Mapped[str | None] = mapped_column(String(255))
    # ID de la ligne de commande fourni par la plateforme de paiement (stable entre les retries).
    item_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    activations: Mapped[list["LicenseActivationRow"]] = relationship(
        back_populates="license", cascade="all, delete-orphan"
    )

    @property
    def edition(self) -> str:
        return "trial" if self.expires_at is not None else "pro"


class LicenseActivationRow(Base):
    __tablename__ = "license_activations"
    # Un Mac n'occupe qu'une seule place par licence : une réactivation réutilise la ligne existante.
    __table_args__ = (
        UniqueConstraint("license_id", "machine_fingerprint", name="uq_license_activations_license_machine"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("act"))
    license_id: Mapped[str] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"), index=True)
    # "SHA256:" suivi de 64 caractères hexadécimaux.
    machine_fingerprint: Mapped[str] = mapped_column(String(80))
    # Informatif, envoyé par l'installeur.
    machine_name: Mapped[str | None] = mapped_column(String(255))
    app_version: Mapped[str | None] = mapped_column(String(32))
    fcpx_version: Mapped[str | None] = mapped_column(String(32))
    macos_version: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    license: Mapped["LicenseRow"] = relationship(back_populates="activations")