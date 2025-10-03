"""安全模块：提供密码哈希、验证以及 JWT 令牌的生成/解析能力。"""

from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from .config import get_settings
from .logger import logger


_refreshed_token_ctx: ContextVar[Optional[str]] = ContextVar("refreshed_token", default=None)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与已存储哈希值是否匹配。"""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """对输入密码执行 bcrypt 哈希并返回可持久化的字符串。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """根据传入载荷生成带有过期时间的签名 JWT。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode = subject.copy()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def store_refreshed_token(token: Optional[str]) -> None:
    """记录当前请求中新生成的访问令牌，供响应阶段附带返回。"""
    _refreshed_token_ctx.set(token)


def consume_refreshed_token() -> Optional[str]:
    """获取并清除当前请求上下文中的刷新令牌。"""
    token = _refreshed_token_ctx.get()
    _refreshed_token_ctx.set(None)
    return token


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解析 JWT 并在合法时返回其中的业务载荷，否则返回 ``None``。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:  # pragma: no cover - logging side effect
        logger.warning("Failed to decode JWT: %s", exc)
        return None
