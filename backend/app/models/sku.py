import uuid
from decimal import Decimal
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Numeric, Integer, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.sales import SalesHistory
    from app.models.inventory import InventorySnapshot
    from app.models.supplier_sku import SupplierSKU
    from app.models.reorder_policy import ReorderPolicy
    from app.models.forecast import Forecast
    from app.models.recommendation import PurchaseRecommendation


class SKU(Base, TimestampMixin):
    """
    Stock Keeping Unit entity representing product catalog master records.
    """
    __tablename__ = "skus"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sku_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pack_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    sales: Mapped[List["SalesHistory"]] = relationship("SalesHistory", back_populates="sku", cascade="all, delete-orphan")
    inventory_snapshots: Mapped[List["InventorySnapshot"]] = relationship("InventorySnapshot", back_populates="sku", cascade="all, delete-orphan")
    supplier_skus: Mapped[List["SupplierSKU"]] = relationship("SupplierSKU", back_populates="sku", cascade="all, delete-orphan")
    reorder_policies: Mapped[List["ReorderPolicy"]] = relationship("ReorderPolicy", back_populates="sku", cascade="all, delete-orphan")
    forecasts: Mapped[List["Forecast"]] = relationship("Forecast", back_populates="sku", cascade="all, delete-orphan")
    recommendations: Mapped[List["PurchaseRecommendation"]] = relationship("PurchaseRecommendation", back_populates="sku")

