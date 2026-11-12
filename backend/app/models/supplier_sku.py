import uuid
from decimal import Decimal
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Numeric, Boolean, Uuid, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.supplier import Supplier
    from app.models.lead_time import LeadTimeObservation


class SupplierSKU(Base, TimestampMixin):
    """
    Contractual link between a Supplier and a SKU, detailing MOQ, pack size, cost and SLA lead time.
    """
    __tablename__ = "supplier_skus"
    __table_args__ = (
        UniqueConstraint("supplier_id", "sku_id", name="uq_supplier_sku"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("skus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pack_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="supplier_skus")
    sku: Mapped["SKU"] = relationship("SKU", back_populates="supplier_skus")
    lead_time_observations: Mapped[List["LeadTimeObservation"]] = relationship(
        "LeadTimeObservation", back_populates="supplier_sku", cascade="all, delete-orphan"
    )

