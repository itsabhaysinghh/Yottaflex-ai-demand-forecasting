import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.sales import SalesHistory
    from app.models.inventory import InventorySnapshot
    from app.models.reorder_policy import ReorderPolicy
    from app.models.forecast import Forecast
    from app.models.recommendation import PurchaseRecommendation


class Store(Base, TimestampMixin):
    """
    Store or distribution center physical location.
    """
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    store_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    store_type: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    warehouse_capacity_units: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    sales: Mapped[List["SalesHistory"]] = relationship("SalesHistory", back_populates="store", cascade="all, delete-orphan")
    inventory_snapshots: Mapped[List["InventorySnapshot"]] = relationship("InventorySnapshot", back_populates="store", cascade="all, delete-orphan")
    reorder_policies: Mapped[List["ReorderPolicy"]] = relationship("ReorderPolicy", back_populates="store", cascade="all, delete-orphan")
    forecasts: Mapped[List["Forecast"]] = relationship("Forecast", back_populates="store", cascade="all, delete-orphan")
    recommendations: Mapped[List["PurchaseRecommendation"]] = relationship("PurchaseRecommendation", back_populates="store")

