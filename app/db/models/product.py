from app.db.models.base import Base

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Interval, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

import uuid
from datetime import datetime, timedelta


def _prefixed_id(prefix: str):
    """Opaque, readable identifiers: ver_3f2a…, pgd_9b5c…"""
    return lambda: f"{prefix}_{uuid.uuid4().hex}"


class ProductVersionRow(Base):
    __tablename__ = "ProductVersion"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("ver"))
    product_id: Mapped[str] = mapped_column(ForeignKey("Product.id", ondelete="CASCADE"), index=True)
    # Display label, e.g. "1.2.0".
    label: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped["ProductRow"] = relationship(back_populates="versions", foreign_keys=[product_id])


class ProductPageDisplayRow(Base):
    __tablename__ = "ProductPageDisplay"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_prefixed_id("pgd"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # URL or path of the icon.
    icon: Mapped[str | None] = mapped_column(String(2048))
    edition_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProductRow(Base):
    """Software (FxPlug plugin) installed on the user's machine."""

    __tablename__ = "Product"

    # FxPlug ID, provided by the application itself.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Current version of the product.
    # Nullable because Product and ProductVersion reference each other: the product row is
    # inserted first, then pointed to its version (use_alter breaks the cycle at CREATE TABLE).
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("ProductVersion.id", ondelete="SET NULL", use_alter=True), index=True
    )
    page_display_id: Mapped[str] = mapped_column(ForeignKey("ProductPageDisplay.id", ondelete="RESTRICT"), index=True)
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    version: Mapped["ProductVersionRow | None"] = relationship(foreign_keys=[version_id], post_update=True)
    versions: Mapped[list["ProductVersionRow"]] = relationship(
        back_populates="product", foreign_keys="ProductVersionRow.product_id", cascade="all, delete-orphan"
    )
    page_display: Mapped["ProductPageDisplayRow"] = relationship()
    licenses: Mapped[list["ProductLicenseRow"]] = relationship(back_populates="product")


class ProductLicenseRow(Base):
    """License offered on the website (one Paddle product) granting access to a Product."""

    __tablename__ = "ProductLicense"
    __table_args__ = (
        CheckConstraint("activation_seats >= 0", name="ck_ProductLicense_activation_seats"),
    )

    # Paddle product ID (pro_…).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("Product.id", ondelete="RESTRICT"), index=True)
    # NULL = perpetual license; otherwise UserLicense.expires_at = created_at + life_duration.
    life_duration: Mapped[timedelta | None] = mapped_column(Interval)
    # Number of machines a license can be activated on, copied into UserLicense.activation_seats.
    activation_seats: Mapped[int] = mapped_column(default=2)

    product: Mapped["ProductRow"] = relationship(back_populates="licenses")
