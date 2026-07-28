"""Shared FastAPI building blocks for Melody services.

Provides request-id propagation, structured JSON logging, a canonical
user-safe error contract, health endpoints, and an app factory that wires
them together.
"""

from .app_factory import create_app
from .errors import AppError, register_exception_handlers
from .health import build_health_router
from .http import DEFAULT_TIMEOUT, make_async_client
from .logging_config import configure_logging
from .request_context import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    get_request_id,
)

__all__ = [
    "create_app",
    "AppError",
    "register_exception_handlers",
    "build_health_router",
    "DEFAULT_TIMEOUT",
    "make_async_client",
    "configure_logging",
    "REQUEST_ID_HEADER",
    "RequestIdMiddleware",
    "get_request_id",
]
