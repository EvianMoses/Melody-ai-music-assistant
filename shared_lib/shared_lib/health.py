"""Liveness and readiness endpoints shared by all services."""

from __future__ import annotations

import inspect
from typing import Awaitable, Callable, Optional, Union

from fastapi import APIRouter
from fastapi.responses import JSONResponse

ReadinessCheck = Callable[[], Union[bool, Awaitable[bool]]]


def build_health_router(readiness: Optional[ReadinessCheck] = None) -> APIRouter:
    """Return a router exposing ``/health/live`` and ``/health/ready``.

    ``readiness`` may be sync or async and should return True when the service's
    dependencies are usable. If omitted, readiness always reports ready.
    """
    router = APIRouter(tags=["health"])

    @router.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready")
    async def ready() -> JSONResponse:
        is_ready = True
        if readiness is not None:
            result = readiness()
            is_ready = await result if inspect.isawaitable(result) else result

        status_code = 200 if is_ready else 503
        return JSONResponse(
            status_code=status_code,
            content={"status": "ready" if is_ready else "not_ready"},
        )

    return router
