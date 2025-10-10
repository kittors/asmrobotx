"""依赖注入模块：封装 FastAPI 中复用度高的依赖函数。"""

from collections.abc import Generator
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.packages.system.core.constants import ACCESS_TOKEN_TYPE
from app.packages.system.core.config import get_settings
from app.packages.system.core.security import (
    decode_token,
    store_current_session_id,
    store_refreshed_token,
    create_access_token,
)
from app.packages.system.core.session import touch_session
from app.packages.system.core.datascope import set_scope as set_data_scope
from app.packages.system.core.constants import ADMIN_ROLE
from app.packages.system.crud.users import user_crud
from app.packages.system.db.session import SessionLocal
from app.packages.system.models.user import User

security_scheme = HTTPBearer(auto_error=False)
settings = get_settings()


def get_db() -> Generator[Session, None, None]:
    """生成一个数据库会话，并在请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 ``Authorization`` 头部并返回当前认证用户，不存在或非法时抛出 401。"""
    store_current_session_id(None)
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证信息")

    if credentials.scheme.lower() != ACCESS_TOKEN_TYPE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证类型无效")

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")

    user = user_crud.get(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    session_id = payload.get("sid")
    if session_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")

    ttl_seconds = max(settings.access_token_expire_minutes, 1) * 60
    if not touch_session(session_id, user.id, ttl_seconds):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    # 记录会话 ID 以便后续使用（例如退出登录）
    store_current_session_id(session_id)

    # 写入数据域上下文，供 CRUD 查询与创建时自动加上组织/创建人信息
    try:
        # 判定是否管理员（按角色名，保持轻量，不阻断请求）
        is_admin = False
        try:
            is_admin = any((role.name or "").lower() == ADMIN_ROLE for role in getattr(user, "roles", []))
        except Exception:
            is_admin = False
        set_data_scope(user_id=user.id, organization_id=getattr(user, "organization_id", None), is_admin=is_admin)
    except Exception:
        # 不影响主流程
        pass

    # 为滑动会话生成一个新的访问令牌，并通过上下文在响应阶段附带返回。
    # 客户端可以选择忽略该 Token（当前实现服务端并不强制令牌轮换）。
    try:
        refreshed_token = create_access_token({"user_id": user.id, "username": user.username, "sid": session_id})
        store_refreshed_token(refreshed_token)
    except Exception:
        # 令牌刷新失败不应影响主流程
        pass

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """确保已认证用户仍处于激活状态，否则拒绝访问。"""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户未激活")
    return current_user
