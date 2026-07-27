"""FastAPI application factory."""

from fastapi import FastAPI

from ksi.api.router import api_router
from ksi.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(api_router)
    return app


app = create_app()
