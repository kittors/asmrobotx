"""异常处理模块：定义统一的业务异常与响应格式。"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from app.packages.system.core.security import consume_refreshed_token


class AppException(HTTPException):
    """携带统一响应结构的业务异常，方便在全局处理中转换响应体。"""

    def __init__(self, msg: str, code: int = status.HTTP_400_BAD_REQUEST, data=None) -> None:
        super().__init__(status_code=code, detail=msg)
        self.data = data


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # pragma: no cover - framework glue
    """将 FastAPI 的 ``HTTPException`` 转换为统一响应格式。"""
    payload = {"msg": exc.detail, "data": getattr(exc, "data", None), "code": exc.status_code}
    token = consume_refreshed_token()
    if token:
        payload["meta"] = {"access_token": token}
    return JSONResponse(status_code=exc.status_code, content=payload)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover - framework glue
    """兜底处理：将未捕获异常转换为标准的 500 响应结构。"""
    payload = {
        "msg": "服务器内部错误",
        "data": None,
        "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    token = consume_refreshed_token()
    if token:
        payload["meta"] = {"access_token": token}
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)
