"""HTTP client for posting canonical request envelopes to the n8n WF-001 webhook."""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class N8nClientError(Exception):
    """Raised when the n8n webhook call fails in a controlled, non-crashing way."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "UPSTREAM_ERROR",
        status_code: int = 502,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_error_envelope(self, request_id: Optional[str] = None) -> dict[str, Any]:
        """User-safe error envelope (Section 3.4 — no stack traces or secrets)."""
        payload: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }
        if request_id:
            payload["request_id"] = request_id
        return payload


class N8nClient:
    """Posts JSON payloads to the configured n8n webhook with explicit timeouts."""

    def __init__(self, webhook_url: str, timeout_seconds: float = 30.0):
        if not webhook_url:
            raise ValueError("N8N webhook URL is required")
        self.webhook_url = webhook_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)

    def post_envelope(self, envelope: dict[str, Any]) -> tuple[Any, int]:
        """POST a request envelope to WF-001.

        Returns:
            (response_body, http_status_code) on success or when n8n returns an
            HTTP error body that should be forwarded.

        Raises:
            N8nClientError: On connection failure, timeout, or unreadable response.
        """
        request_id = envelope.get("request_id")
        try:
            response = requests.post(
                self.webhook_url,
                json=envelope,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
            )
        except requests.Timeout:
            logger.warning(
                "n8n webhook timed out after %.1fs (request_id=%s)",
                self.timeout_seconds,
                request_id,
            )
            raise N8nClientError(
                "The recommendation orchestrator timed out. Please try again.",
                code="UPSTREAM_TIMEOUT",
                status_code=504,
            ) from None
        except requests.ConnectionError:
            logger.warning(
                "n8n webhook connection failed (request_id=%s)",
                request_id,
            )
            raise N8nClientError(
                "Could not reach the recommendation orchestrator.",
                code="UPSTREAM_UNAVAILABLE",
                status_code=502,
            ) from None
        except requests.RequestException as error:
            logger.warning(
                "n8n webhook request failed (request_id=%s): %s",
                request_id,
                type(error).__name__,
            )
            raise N8nClientError(
                "The recommendation orchestrator request failed.",
                code="UPSTREAM_ERROR",
                status_code=502,
            ) from None

        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: requests.Response) -> tuple[Any, int]:
        content_type = (response.headers.get("Content-Type") or "").lower()
        try:
            if "application/json" in content_type or response.text.strip().startswith(
                ("{", "[")
            ):
                body: Any = response.json()
            else:
                body = {"raw": response.text}
        except ValueError:
            raise N8nClientError(
                "The recommendation orchestrator returned an invalid response.",
                code="UPSTREAM_INVALID_RESPONSE",
                status_code=502,
            ) from None

        return body, response.status_code
