import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Integer, Boolean, Date, DateTime, func, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.supplier_sku import SupplierSKU


class LeadTimeObservation(Base):
    """
    Empirical purchase order fulfillment record used to calculate lead time mean and standard deviation.
    """
    __tablename__ = "lead_time_observations"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    supplier_sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("supplier_skus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    promised_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    units_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    units_received: Mapped[int] = mapped_column(Integer, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    supplier_sku: Mapped["SupplierSKU"] = relationship("SupplierSKU", back_populates="lead_time_observations")
