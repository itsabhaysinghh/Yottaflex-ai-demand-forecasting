from fastapi import APIRouter

from app.api.v1.endpoints import (
    overview,
    skus,
    stores,
    suppliers,
    inventory,
    sales,
    forecasts,
    recommendations,
    exceptions,
)

api_router = APIRouter()

api_router.include_router(overview.router, prefix="/overview", tags=["Overview Dashboard"])
api_router.include_router(skus.router, prefix="/skus", tags=["SKUs"])
api_router.include_router(stores.router, prefix="/stores", tags=["Stores"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(sales.router, prefix="/sales", tags=["Sales History"])
api_router.include_router(forecasts.router, prefix="/forecasts", tags=["Demand Forecasts"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Replenishment Recommendations"])
api_router.include_router(exceptions.router, prefix="/exceptions", tags=["Exceptions & Risk"])

