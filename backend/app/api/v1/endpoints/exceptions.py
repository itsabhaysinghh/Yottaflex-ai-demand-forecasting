from datetime import datetime, timezone
import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.exception import InventoryException
from app.models.sku import SKU
from app.models.store import Store
from app.schemas.exception import InventoryExceptionResponse, ExceptionResolveRequest
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[InventoryExceptionResponse])
def list_exceptions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    exception_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = (
        select(
            InventoryException,
            SKU.sku_code.label("sku_code"),
            Store.store_code.label("store_code"),
        )
        .outerjoin(SKU, InventoryException.sku_id == SKU.id)
        .outerjoin(Store, InventoryException.store_id == Store.id)
    )

    if severity:
        query = query.where(InventoryException.severity == severity)
    if is_resolved is not None:
        query = query.where(InventoryException.is_resolved == is_resolved)
    if exception_type:
        query = query.where(InventoryException.exception_type == exception_type)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.order_by(InventoryException.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for exc, sku_code, store_code in rows:
        resp = InventoryExceptionResponse.model_validate(exc)
        resp.sku_code = sku_code
        resp.store_code = store_code
        items.append(resp)

    return PaginatedResponse[InventoryExceptionResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.patch("/{exc_id}/resolve", response_model=InventoryExceptionResponse)
def resolve_exception(
    exc_id: uuid.UUID,
    payload: ExceptionResolveRequest,
    db: Session = Depends(get_db),
):
    exc = db.get(InventoryException, exc_id)
    if not exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exc_id} not found",
        )

    exc.is_resolved = True
    exc.resolved_by = payload.resolved_by
    exc.resolved_at = datetime.now(timezone.utc)
    if payload.resolution_notes:
        if not exc.payload:
            exc.payload = {}
        exc.payload["resolution_notes"] = payload.resolution_notes

    db.commit()
    db.refresh(exc)

    resp = InventoryExceptionResponse.model_validate(exc)
    if exc.sku:
        resp.sku_code = exc.sku.sku_code
    if exc.store:
        resp.store_code = exc.store.store_code
    return resp

