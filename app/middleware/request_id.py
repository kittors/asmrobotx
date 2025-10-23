"""Request ID middleware: injects X-Request-ID into context for logging.

If incoming request has X-Request-ID header, reuse it; otherwise generate a UUID4.
The value is exposed via app logger's RequestIdFilter.
"""

from __future__ import annotations

import uuid
from typing import Callable, Awaitable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.packages.system.core.logger import set_request_id


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # pragma: no cover
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        try:
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            rid = headers.get("x-request-id") or str(uuid.uuid4())
            set_request_id(rid)
        except Exception:
            pass
        await self.app(scope, receive, send)

