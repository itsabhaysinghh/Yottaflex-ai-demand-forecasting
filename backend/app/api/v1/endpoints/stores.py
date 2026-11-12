import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.store import Store
from app.schemas.store import StoreResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[StoreResponse])
def list_stores(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    store_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = select(Store)
    if store_type:
        query = query.where(Store.store_type == store_type)
    if is_active is not None:
        query = query.where(Store.is_active == is_active)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    items = db.scalars(
        query.order_by(Store.store_code).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse[StoreResponse](
        items=[StoreResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{store_id}", response_model=StoreResponse)
def get_store(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Store {store_id} not found")
    return StoreResponse.model_validate(store)

