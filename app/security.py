"""Anonymous browser-session ownership for public user testing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SessionSettings:
    secret: bytes
    cookie_name: str
    secure: bool
    max_age_seconds: int


def build_session_settings() -> SessionSettings:
    load_dotenv()
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    configured_secret = os.getenv("SESSION_SECRET", "").strip()
    if not configured_secret and environment == "production":
        raise RuntimeError("SESSION_SECRET is required when ENVIRONMENT=production.")
    if environment == "production" and len(configured_secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "SESSION_SECRET must contain at least 32 bytes when ENVIRONMENT=production."
        )
    if not configured_secret:
        configured_secret = secrets.token_urlsafe(48)
        logger.warning(
            "SESSION_SECRET is not configured; anonymous sessions will reset on restart."
        )

    retention_days = int(os.getenv("PLAN_RETENTION_DAYS", "30"))
    return SessionSettings(
        secret=configured_secret.encode("utf-8"),
        cookie_name=os.getenv("SESSION_COOKIE_NAME", "studygrid_session"),
        secure=_env_bool("SESSION_COOKIE_SECURE", environment == "production"),
        max_age_seconds=retention_days * 24 * 60 * 60,
    )


class AnonymousSessionMiddleware(BaseHTTPMiddleware):
    """Attach a signed, HttpOnly anonymous owner id to API requests."""

    def __init__(self, app: object) -> None:
        super().__init__(app)
        self.settings = build_session_settings()

    def _sign(self, owner_id: str) -> str:
        digest = hmac.new(
            self.settings.secret, owner_id.encode("ascii"), hashlib.sha256
        ).digest()
        signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"{owner_id}.{signature}"

    def _verify(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            owner_id, supplied = token.split(".", 1)
        except ValueError:
            return None
        if len(owner_id) != 32 or any(char not in "0123456789abcdef" for char in owner_id):
            return None
        expected = self._sign(owner_id).split(".", 1)[1]
        return owner_id if hmac.compare_digest(supplied, expected) else None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        token = request.cookies.get(self.settings.cookie_name)
        owner_id = self._verify(token)
        is_new = owner_id is None
        if owner_id is None:
            owner_id = secrets.token_hex(16)
        request.state.owner_id = owner_id

        response = await call_next(request)
        if is_new and request.url.path.startswith("/api/"):
            response.set_cookie(
                self.settings.cookie_name,
                self._sign(owner_id),
                max_age=self.settings.max_age_seconds,
                httponly=True,
                secure=self.settings.secure,
                samesite="lax",
                path="/",
            )
        return response


def get_owner_id(request: Request) -> str:
    """FastAPI dependency exposing the owner id established by middleware."""
    owner_id = getattr(request.state, "owner_id", None)
    if not isinstance(owner_id, str):
        raise RuntimeError("Anonymous session middleware is not installed.")
    return owner_id


def clear_session_cookie(response: Response) -> None:
    """Expire the browser identifier after all owned data is deleted."""
    response.delete_cookie(
        os.getenv("SESSION_COOKIE_NAME", "studygrid_session"),
        path="/",
        samesite="lax",
    )
