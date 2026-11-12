import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Integer, Boolean, Date, DateTime, func, Uuid, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.store import Store


class InventorySnapshot(Base):
    """
    Daily snapshot of inventory positions, in-transit stock, and stockout occurrences.
    """
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint("sku_id", "store_id", "snapshot_date", name="uq_inv_sku_store_date"),
        Index("idx_inv_sku_store_date", "sku_id", "store_id", "snapshot_date"),
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
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    opening_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    closing_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    in_transit_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stockout_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    lost_sales_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    sku: Mapped["SKU"] = relationship("SKU", back_populates="inventory_snapshots")
    store: Mapped["Store"] = relationship("Store", back_populates="inventory_snapshots")
