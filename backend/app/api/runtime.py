"""Request IDs, safe errors, shared-token access and bounded in-process throttling."""

import json
import logging
import secrets
from collections import OrderedDict, deque
from time import monotonic, perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.core.config import Settings
from backend.app.core.errors import (
    CitationValidationError,
    ModelConfigurationError,
    ModelServiceError,
)

logger = logging.getLogger("copilot.requests")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


class SlidingWindowLimiter:
    def __init__(self, limit: int, *, max_clients: int = 10000) -> None:
        self.limit = limit
        self.max_clients = max_clients
        self._clients: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, client: str, now: float) -> bool:
        # Called only from the event-loop middleware, without await between mutations.
        while self._clients:
            oldest = next(iter(self._clients))
            if self._clients[oldest][-1] > now - 60:
                break
            self._clients.popitem(last=False)
        if client not in self._clients:
            if len(self._clients) >= self.max_clients:
                return False
            self._clients[client] = deque()
        history = self._clients[client]
        while history and history[0] <= now - 60:
            history.popleft()
        if len(history) >= self.limit:
            return False
        history.append(now)
        self._clients.move_to_end(client)
        return True

    def clear(self) -> None:
        self._clients.clear()


def _error(request: Request, status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"detail": message, "request_id": request.state.request_id},
    )


def install_runtime(application: FastAPI, settings: Settings) -> None:
    application.state.limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)
    access_token = (
        settings.api_access_token.get_secret_value().strip() if settings.api_access_token else ""
    )

    @application.exception_handler(CitationValidationError)
    async def invalid_citation(request: Request, exc: CitationValidationError) -> JSONResponse:
        return _error(request, 502, "回答引用校验失败，请重试或联系服务维护者。")

    @application.exception_handler(ModelConfigurationError)
    async def invalid_model_config(request: Request, exc: ModelConfigurationError) -> JSONResponse:
        return _error(request, 503, "模型服务尚未正确配置，请联系服务维护者。")

    @application.exception_handler(ModelServiceError)
    async def model_unavailable(request: Request, exc: ModelServiceError) -> JSONResponse:
        return _error(request, 503, "模型服务暂时不可用，请稍后重试。")

    @application.middleware("http")
    async def request_boundary(request: Request, call_next):
        started = perf_counter()
        request.state.request_id = uuid4().hex
        path = request.url.path
        protected = path.startswith(settings.api_prefix + "/") and path != (
            settings.api_prefix + "/health"
        )
        try:
            if (
                protected
                and access_token
                and not secrets.compare_digest(
                    request.headers.get("Authorization", "").encode(),
                    f"Bearer {access_token}".encode(),
                )
            ):
                response = _error(request, 401, "请提供正确的访问口令。")
                response.headers["WWW-Authenticate"] = "Bearer"
            elif protected and not application.state.limiter.allow(
                request.client.host if request.client else "unknown", monotonic()
            ):
                response = _error(request, 429, "请求过于频繁，请稍后再试。")
                response.headers["Retry-After"] = "60"
            else:
                response = await call_next(request)
        except Exception:
            # Do not emit exception messages, input, headers or model response bodies.
            response = _error(request, 500, "服务处理失败，请凭请求编号联系维护者。")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
        if protected:
            response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        if (
            route_path != "unmatched"
            and path.startswith(settings.api_prefix + "/")
            and not route_path.startswith(settings.api_prefix + "/")
        ):
            route_path = settings.api_prefix + route_path
        logger.info(
            json.dumps(
                {
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "route": route_path,
                    "status": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
        )
        return response
