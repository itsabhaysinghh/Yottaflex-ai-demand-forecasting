import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Numeric, Boolean, Uuid, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.store import Store


class ReorderPolicy(Base, TimestampMixin):
    """
    Inventory replenishment parameters and target service levels per SKU and Store.
    """
    __tablename__ = "reorder_policies"
    __table_args__ = (
        UniqueConstraint("sku_id", "store_id", name="uq_reorder_policy_sku_store"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
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
    target_service_level: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.950"), nullable=False)
    review_period_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    lead_time_override_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_safety_stock_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_safety_stock_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    sku: Mapped["SKU"] = relationship("SKU", back_populates="reorder_policies")
    store: Mapped["Store"] = relationship("Store", back_populates="reorder_policies")

