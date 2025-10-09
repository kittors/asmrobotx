"""认证相关路由定义。"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    LogoutResponse,
)
from app.packages.system.core.dependencies import get_db, get_current_active_user
from app.packages.system.core.constants import HTTP_STATUS_OK
from app.packages.system.core.timezone import now as tz_now
from app.packages.system.core.responses import create_response
from app.packages.system.services.auth_service import auth_service
from app.packages.system.models.user import User
from app.packages.system.core.security import get_current_session_id
from app.packages.system.core.session import delete_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    """调用认证服务完成注册流程并返回统一响应。"""
    return auth_service.register_user(
        db,
        username=payload.username,
        password=payload.password,
        organization_id=payload.organization_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """校验凭证并签发访问令牌。"""
    client_meta = _extract_login_meta(request)
    return auth_service.login(
        db,
        username=payload.username,
        password=payload.password,
        client_meta=client_meta,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(current_user: User = Depends(get_current_active_user)) -> LogoutResponse:
    """退出登录，前端需删除本地缓存的令牌。"""
    session_id = get_current_session_id()
    if session_id:
        delete_session(session_id)
    return create_response("退出登录成功", None, HTTP_STATUS_OK)


def _extract_login_meta(request: Request) -> Dict[str, Any]:
    """从请求中提取用于记录登录日志的上下文信息。"""

    ip_address = _extract_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    operating_system = _guess_operating_system(user_agent)
    browser = _guess_browser(user_agent)
    device_type = "mobile" if "mobile" in user_agent.lower() else "pc"

    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "operating_system": operating_system,
        "browser": browser,
        "device_type": device_type,
        "client_name": "web",
        "login_time": tz_now(),
    }


def _extract_client_ip(request: Request) -> Optional[str]:
    header_keys = [
        "x-forwarded-for",
        "x-real-ip",
        "x-client-ip",
    ]
    for key in header_keys:
        raw = request.headers.get(key)
        if raw:
            return raw.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _guess_operating_system(user_agent: str) -> Optional[str]:
    ua = user_agent.lower()
    if not ua:
        return None
    if "windows" in ua:
        return "Windows"
    if "mac os" in ua or "macintosh" in ua:
        return "macOS"
    if "iphone" in ua or "ios" in ua:
        return "iOS"
    if "android" in ua:
        return "Android"
    if "linux" in ua:
        return "Linux"
    return None


def _guess_browser(user_agent: str) -> Optional[str]:
    ua = user_agent.lower()
    if not ua:
        return None
    if "chrome" in ua and "safari" in ua and "edge" not in ua:
        return "Chrome"
    if "safari" in ua and "chrome" not in ua:
        return "Safari"
    if "firefox" in ua:
        return "Firefox"
    if "edge" in ua or "edg" in ua:
        return "Edge"
    if "msie" in ua or "trident" in ua:
        return "Internet Explorer"
    return None
