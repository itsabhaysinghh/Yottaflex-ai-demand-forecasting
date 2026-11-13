import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import BigInteger, String, Integer, Numeric, Date, DateTime, func, Uuid, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ForecastEvaluation(Base):
    """
    Historical backtest evaluation metrics per model, SKU and Store.
    """
    __tablename__ = "forecast_evaluations"
    __table_args__ = (
        UniqueConstraint("sku_id", "store_id", "model_name", "evaluation_date", "horizon_days", name="uq_forecast_eval"),
        Index("idx_eval_lookup", "model_name", "evaluation_date"),
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
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evaluation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    rmse: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    wape: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    bias: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
