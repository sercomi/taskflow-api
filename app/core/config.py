from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TaskFlow API"
    app_version: str = "0.1.0"
    app_description: str = "REST API for collaborative project and task management"

    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    postgres_db: str = "taskflow"
    postgres_user: str = "taskflow"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    jwt_secret_key: str = ""
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, gt=0)

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def database_url(self) -> URL:
        if not self.postgres_password:
            raise ValueError("POSTGRES_PASSWORD environment variable is required")

        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.is_production:
            if not self.jwt_secret_key:
                raise ValueError("JWT_SECRET_KEY is required in production")

            if len(self.jwt_secret_key.encode("utf-8")) < 32:
                raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes in production")

            if self.debug:
                raise ValueError("DEBUG must be disabled in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
