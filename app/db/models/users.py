from app.db.models.base import Base
# Imported so the Product tables are registered before the foreign keys below are resolved.
from app.db.models.product import ProductLicenseRow, ProductRow

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

import uuid
from datetime import datetime


def _prefixed_id(prefix: str):
    """Opaque, readable identifiers: lic_3f2a…, act_9b5c…"""
    return lambda: f"{prefix}_{uuid.uuid4().hex}"


class UserRow(Base):
    __tablename__ = "User"

    # Paddle customer ID (ctm_…).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    # Full name, as given by Paddle.
    name: Mapped[str | None] = mapped_column(String(255))
    # Marketing consent.
    marketing: Mapped[bool] = mapped_column(default=False)
    # Set by the DB when the customer is first inserted, never updated.
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    licenses: Mapped[list["UserLicenseRow"]] = relationship(back_populates="user")


class UserLicenseRow(Base):
    __tablename__ = "UserLicense"
    __table_args__ = (
        CheckConstraint("activation_seats >= 0", name="ck_UserLicense_activation_seats"),
        # One license per order line: a webhook retry does not create a duplicate.
        UniqueConstraint("order_id", "product_license_id", name="uq_UserLicense_order_product_license"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("lic"))
    # License offered on the website (Paddle product ID).
    product_license_id: Mapped[str] = mapped_column(ForeignKey("ProductLicense.id", ondelete="RESTRICT"), index=True)
    # Paddle transaction ID (txn_…).
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("User.id", ondelete="RESTRICT"), index=True)
    # Software unlocked by the license (FxPlug ID), copied from ProductLicense.product_id.
    product_id: Mapped[str] = mapped_column(ForeignKey("Product.id", ondelete="RESTRICT"), index=True)
    # Secret: stored uppercase (format XXXX-XXXX-XXXX-XXXX), never placed in the token.
    license_key: Mapped[str] = mapped_column(String(64), unique=True)
    activation_seats: Mapped[int] = mapped_column(default=2)
    # NULL = perpetual license; a date = trial (copied into the token's expiresAt).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["UserRow"] = relationship(back_populates="licenses")
    product_license: Mapped["ProductLicenseRow"] = relationship()
    product: Mapped["ProductRow"] = relationship()
    activations: Mapped[list["UserActivationRow"]] = relationship(
        back_populates="license", cascade="all, delete-orphan"
    )

    @property
    def edition(self) -> str:
        return "trial" if self.expires_at is not None else "pro"


class UserMachineRow(Base):
    __tablename__ = "UserMachine"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("mac"))
    # Informative, sent by the installer.
    machine_name: Mapped[str | None] = mapped_column(String(255))
    # "SHA256:" followed by 64 hex characters.
    machine_fingerprint: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    activations: Mapped[list["UserActivationRow"]] = relationship(back_populates="machine")


class UserActivationRow(Base):
    __tablename__ = "UserActivation"
    # A machine only takes one seat per license: a reactivation reuses the existing row.
    __table_args__ = (
        UniqueConstraint("license_id", "machine_id", name="uq_UserActivation_license_machine"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("act"))
    license_id: Mapped[str] = mapped_column(ForeignKey("UserLicense.id", ondelete="CASCADE"), index=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("UserMachine.id", ondelete="CASCADE"), index=True)
    # Informative, sent by the installer.
    app_version: Mapped[str | None] = mapped_column(String(32))
    fcpx_version: Mapped[str | None] = mapped_column(String(32))
    macos_version: Mapped[str | None] = mapped_column(String(128))
    last_activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    license: Mapped["UserLicenseRow"] = relationship(back_populates="activations")
    machine: Mapped["UserMachineRow"] = relationship(back_populates="activations")
