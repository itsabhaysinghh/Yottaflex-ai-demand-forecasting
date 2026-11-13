import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.supplier import Supplier
from app.models.supplier_sku import SupplierSKU
from app.models.sku import SKU
from app.schemas.supplier import SupplierResponse, SupplierSKUResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SupplierResponse])
def list_suppliers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(Supplier)
    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
    if search:
        query = query.where(
            Supplier.name.ilike(f"%{search}%") | Supplier.supplier_code.ilike(f"%{search}%")
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    items = db.scalars(
        query.order_by(Supplier.supplier_code).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse[SupplierResponse](
        items=[SupplierResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: uuid.UUID, db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.get("/{supplier_id}/skus", response_model=PaginatedResponse[SupplierSKUResponse])
def list_supplier_skus(
    supplier_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = (
        select(SupplierSKU, SKU.sku_code.label("sku_code"))
        .join(SKU, SupplierSKU.sku_id == SKU.id)
        .where(SupplierSKU.supplier_id == supplier_id)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for supplier_sku, sku_code in rows:
        response = SupplierSKUResponse.model_validate(supplier_sku)
        response.sku_code = sku_code
        items.append(response)

    return PaginatedResponse[SupplierSKUResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
