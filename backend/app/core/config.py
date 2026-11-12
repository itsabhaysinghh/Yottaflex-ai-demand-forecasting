from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


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
    POSTGRES_USER: str = "yottaflex"
    POSTGRES_PASSWORD: str = ""
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

    @property
    def effective_database_url(self) -> str:
        """
        Returns the configured URL, normalizing PostgreSQL connections to psycopg 3.
        """
        if self.DATABASE_URL:
            url = make_url(self.DATABASE_URL)
            if url.get_backend_name() == "postgresql":
                url = url.set(drivername="postgresql+psycopg")
            return url.render_as_string(hide_password=False)

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


settings = Settings()
