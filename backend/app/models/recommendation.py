import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, TYPE_CHECKING
from sqlalchemy import String, Integer, Numeric, Date, DateTime, Text, Uuid, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.store import Store
    from app.models.supplier import Supplier
    from app.models.reorder_policy import ReorderPolicy


class PurchaseRecommendation(Base, TimestampMixin):
    """
    Explainable replenishment order recommendations with approval lifecycle.
    """
    __tablename__ = "purchase_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reorder_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reorder_policies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    recommendation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    current_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    current_on_order: Mapped[int] = mapped_column(Integer, nullable=False)
    net_inventory_position: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_demand: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_units: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False, index=True)
    explanation: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    sku: Mapped["SKU"] = relationship("SKU", back_populates="recommendations")
    store: Mapped["Store"] = relationship("Store", back_populates="recommendations")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="recommendations")

