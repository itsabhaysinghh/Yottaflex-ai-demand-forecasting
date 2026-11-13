from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks if needed
    yield
    # Shutdown tasks if needed


fastapi_app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Retail Inventory Intelligence Platform: Demand forecasting baselines, "
        "statistical safety stock, reorder point replenishment, and explainable purchase decisions."
    ),
    lifespan=lifespan,
)

# Register API v1 routes
fastapi_app.include_router(api_router, prefix="/api/v1")


@fastapi_app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs_url": "/docs",
    }


@fastapi_app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "dataset_profile": settings.DATASET_PROFILE,
        "random_seed": settings.RANDOM_SEED,
    }


# Wrap the complete application so CORS headers are also added to unhandled 500 responses.
app = CORSMiddleware(
    app=fastapi_app,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)

