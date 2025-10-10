"""应用入口：负责创建 FastAPI 实例并绑定生命周期事件。"""

from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from app.packages import get_active_package

package = get_active_package()
package.setup_logging()
settings = package.get_settings()
logger = package.logger
init_db = package.init_db
api_router = package.api_router
create_response = package.create_response
http_exception_handler = package.http_exception_handler
generic_exception_handler = package.generic_exception_handler
from app.packages.system.core.security import consume_refreshed_token
from app.middleware.datascope import DataScopeMiddleware

app = FastAPI(title=settings.project_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Access-Token"],
)

app.add_middleware(DataScopeMiddleware)

class AccessTokenHeaderMiddleware(BaseHTTPMiddleware):
    """将当前请求上下文中的刷新令牌附加到响应头中。

    若上游业务在本次请求内生成了新的访问令牌（滑动续期或登录成功），
    则通过上下文变量暴露；本中间件会统一把该值写入响应头 `X-Access-Token`，
    以便前端可选地接收并替换本地缓存。
    """

    async def dispatch(self, request, call_next):  # pragma: no cover - 框架胶水代码
        response = await call_next(request)
        token = consume_refreshed_token()
        if token:
            response.headers["X-Access-Token"] = token
        return response


app.add_middleware(AccessTokenHeaderMiddleware)


@app.on_event("startup")
async def startup_event() -> None:
    """初始化数据库状态，确认服务可用后输出成功日志。"""
    init_db()
    # 从本地存储的“目录操作记录文件”导入到数据库（若存在）
    try:
        from app.packages.system.db import session as db_session
        from app.packages.system.services.dir_log_ingestor import ingest_local_dir_logs

        with db_session.SessionLocal() as s:
            imported = ingest_local_dir_logs(s)
            if imported:
                logger.info("Imported %s directory change records from local storage logs", imported)
    except Exception:
        logger.warning("Failed to import directory change records on startup", exc_info=True)
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
