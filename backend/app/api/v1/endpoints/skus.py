import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.sku import SKU
from app.schemas.sku import SKUResponse, SKUCreate, SKUUpdate
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SKUResponse])
def list_skus(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(SKU)
    if category:
        query = query.where(SKU.category == category)
    if is_active is not None:
        query = query.where(SKU.is_active == is_active)
    if search:
        query = query.where(
            SKU.name.ilike(f"%{search}%") | SKU.sku_code.ilike(f"%{search}%")
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    items = db.scalars(
        query.order_by(SKU.sku_code).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse[SKUResponse](
        items=[SKUResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{sku_id}", response_model=SKUResponse)
def get_sku(sku_id: uuid.UUID, db: Session = Depends(get_db)):
    sku = db.get(SKU, sku_id)
    if not sku:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SKU {sku_id} not found")
    return SKUResponse.model_validate(sku)

