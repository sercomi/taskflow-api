from fastapi import FastAPI

from app.core.config import settings


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        debug=settings.debug,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    return application


app = create_application()
