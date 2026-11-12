import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, TYPE_CHECKING
from sqlalchemy import String, Integer, Numeric, Date, DateTime, func, Uuid, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.store import Store


class Forecast(Base):
    """
    Persisted demand forecast predictions and intervals.
    """
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("sku_id", "store_id", "model_name", "forecast_date", "target_date", name="uq_forecast_run"),
        Index("idx_forecast_lookup", "sku_id", "store_id", "forecast_date", "target_date"),
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
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    confidence_lower: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    confidence_upper: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    model_params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    sku: Mapped["SKU"] = relationship("SKU", back_populates="forecasts")
    store: Mapped["Store"] = relationship("Store", back_populates="forecasts")

