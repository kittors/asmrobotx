"""依赖注入模块：封装 FastAPI 中复用度高的依赖函数。"""

from collections.abc import Generator
from typing import Optional

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.constants import ACCESS_TOKEN_TYPE
from app.core.security import create_access_token, decode_token, store_refreshed_token
from app.crud.users import user_crud
from app.db.session import SessionLocal
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """生成一个数据库会话，并在请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 ``Authorization`` 头部并返回当前认证用户，不存在或非法时抛出 401。"""
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

    refreshed_token = create_access_token({"user_id": user.id, "username": user.username})
    response.headers["X-Access-Token"] = refreshed_token
    store_refreshed_token(refreshed_token)

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """确保已认证用户仍处于激活状态，否则拒绝访问。"""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户未激活")
    return current_user
