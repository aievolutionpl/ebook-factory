"""HTTP Basic auth guarding the whole app except `/health`.

Credentials come from the environment (EBOOK_FACTORY_AUTH_USER /
EBOOK_FACTORY_AUTH_PASSWORD) so nothing secret ever lives in source or
deploy scripts. `/health` stays public so uptime checks and load balancers
don't need credentials.
"""

from __future__ import annotations

import base64
import binascii
import os
import secrets
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

PUBLIC_PATHS = {"/health"}


def credentials_from_env() -> Optional[tuple[str, str]]:
    user = os.environ.get("EBOOK_FACTORY_AUTH_USER")
    password = os.environ.get("EBOOK_FACTORY_AUTH_PASSWORD")
    if user and password:
        return (user, password)
    return None


class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, credentials: tuple[str, str]) -> None:
        super().__init__(app)
        self._user, self._password = credentials

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if self._is_authorized(request.headers.get("authorization")):
            return await call_next(request)
        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})

    def _is_authorized(self, header: Optional[str]) -> bool:
        if not header or not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[len("Basic "):], validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False
        user, sep, password = decoded.partition(":")
        if not sep:
            return False
        return secrets.compare_digest(user, self._user) and secrets.compare_digest(
            password, self._password
        )
