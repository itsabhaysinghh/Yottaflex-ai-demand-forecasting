import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Integer, Numeric, Boolean, Date, DateTime, func, Uuid, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.store import Store


class SalesHistory(Base):
    """
    Daily aggregated sales transactions per SKU and Store.
    """
    __tablename__ = "sales_history"
    __table_args__ = (
        UniqueConstraint("sku_id", "store_id", "sale_date", name="uq_sales_sku_store_date"),
        Index("idx_sales_sku_store_date", "sku_id", "store_id", "sale_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("skus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_promotion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promotion_discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    sku: Mapped["SKU"] = relationship("SKU", back_populates="sales")
    store: Mapped["Store"] = relationship("Store", back_populates="sales")
