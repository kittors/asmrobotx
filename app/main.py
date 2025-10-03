"""应用入口：负责创建 FastAPI 实例并绑定生命周期事件。"""

from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.exceptions import generic_exception_handler, http_exception_handler
from app.core.logger import setup_logging, logger
from app.core.responses import create_response
from app.db.init_db import init_db

setup_logging()
settings = get_settings()

app = FastAPI(title=settings.project_name, debug=settings.debug)


@app.on_event("startup")
async def startup_event() -> None:
    """初始化数据库状态，确认服务可用后输出成功日志。"""
    init_db()
    logger.info("SUCCESS - Application running at http://127.0.0.1:%s", settings.app_port)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc):  # pragma: no cover - framework glue
    """将 ``HTTPException`` 转换为统一的响应结构。"""
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def custom_generic_exception_handler(request, exc):  # pragma: no cover - framework glue
    """捕获未预料异常并包装为标准错误响应。"""
    return await generic_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):  # pragma: no cover - framework glue
    """统一处理请求体验证失败的场景。"""
    def _serialize(obj: Any) -> Any:
        if isinstance(obj, Exception):
            return str(obj)
        if isinstance(obj, dict):
            return {key: _serialize(value) for key, value in obj.items()}
        if isinstance(obj, list):
            return [_serialize(item) for item in obj]
        return obj

    serialized_errors = _serialize(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_response("请求参数验证失败", serialized_errors, status.HTTP_422_UNPROCESSABLE_ENTITY),
    )


@app.get("/health")
async def health_check() -> dict:
    """提供健康检查接口，便于编排器与监控系统探活。"""
    return create_response("OK", {"status": "healthy"})


app.include_router(api_router, prefix=settings.api_v1_str)
