from pathlib import Path
from typing import List, Union
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root path (where .env is located)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """
    Application settings and environment configurations.
    All properties can be overridden by environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "YottaFlex Demand Forecasting & Replenishment System"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # PostgreSQL Credentials
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "yottaflex_secure_password"
    POSTGRES_DB: str = "yottaflex_demand"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Database URL override (if explicitly specified in .env)
    DATABASE_URL: str | None = None

    # SQLite fallback URL (for lightweight testing if configured)
    SQLITE_DATABASE_URL: str = "sqlite:///./yottaflex_dev.db"

    # Synthetic Data Generation
    RANDOM_SEED: int = 20261022
    DATASET_PROFILE: str = "dev"  # 'dev' (100 SKUs, 10 stores, 90 days) or 'full'

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @computed_field
    @property
    def effective_database_url(self) -> str:
        """
        Returns the configured DATABASE_URL or constructs the PostgreSQL connection string.
        Defaults to postgresql+psycopg2 driver for maximum Windows OS compatibility.
        """
        if self.DATABASE_URL:
            # If specified as postgresql+psycopg://, adapt to postgresql+psycopg2 if needed
            url = self.DATABASE_URL
            if url.startswith("postgresql+psycopg://"):
                url = url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()

