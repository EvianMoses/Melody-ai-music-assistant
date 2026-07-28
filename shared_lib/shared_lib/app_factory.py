"""Factory that assembles a Melody service FastAPI app with shared concerns."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI

from .errors import register_exception_handlers
from .health import ReadinessCheck, build_health_router
from .logging_config import configure_logging
from .request_context import RequestIdMiddleware


def create_app(
    title: str,
    *,
    version: str = "0.1.0",
    readiness: Optional[ReadinessCheck] = None,
) -> FastAPI:
    """Create a FastAPI app wired with logging, request-id, errors, and health."""
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    app = FastAPI(title=title, version=version)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(build_health_router(readiness))

    return app
