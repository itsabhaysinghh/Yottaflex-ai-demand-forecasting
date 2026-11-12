import uuid
from decimal import Decimal
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Numeric, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.supplier_sku import SupplierSKU
    from app.models.recommendation import PurchaseRecommendation


class Supplier(Base, TimestampMixin):
    """
    Vendor master entity providing supplier profiles and default performance SLAs.
    """
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    supplier_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.95"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    supplier_skus: Mapped[List["SupplierSKU"]] = relationship("SupplierSKU", back_populates="supplier", cascade="all, delete-orphan")
    recommendations: Mapped[List["PurchaseRecommendation"]] = relationship("PurchaseRecommendation", back_populates="supplier")

