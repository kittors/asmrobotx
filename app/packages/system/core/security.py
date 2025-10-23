"""安全模块：提供密码哈希、验证以及 JWT 令牌的生成/解析能力。"""

from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from .config import get_settings
from .logger import logger


_refreshed_token_ctx: ContextVar[Optional[str]] = ContextVar("refreshed_token", default=None)
_session_id_ctx: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


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


def create_temporary_token(subject: Dict[str, Any], *, expires_seconds: int = 600) -> str:
    """创建一个短期有效的 JWT，用于临时直链等场景。

    注意：该令牌不绑定用户会话，仅用于资源级别的临时授权。
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(seconds=max(int(expires_seconds or 0), 1))
    payload = subject.copy()
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def store_refreshed_token(token: Optional[str]) -> None:
    """记录当前请求中新生成的访问令牌，供响应阶段附带返回。"""
    _refreshed_token_ctx.set(token)


def consume_refreshed_token() -> Optional[str]:
    """获取当前请求上下文中的刷新令牌。"""
    return _refreshed_token_ctx.get()


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解析 JWT 并在合法时返回其中的业务载荷，否则返回 ``None``。"""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        return payload
    except JWTError as exc:  # pragma: no cover - logging side effect
        logger.warning("Failed to decode JWT: %s", exc)
        return None


def decode_and_verify_token(token: str, *, verify_exp: bool = True) -> Optional[Dict[str, Any]]:
    """解码并校验 JWT，默认校验过期时间。

    与 ``decode_token`` 不同，该函数会根据 ``verify_exp`` 决定是否验证 ``exp``。适合用于直链签名等需要严格过期控制的场景。
    """
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": verify_exp},
        )
    except JWTError as exc:  # pragma: no cover - logging side effect
        logger.warning("Failed to verify JWT: %s", exc)
        return None


def store_current_session_id(session_id: Optional[str]) -> None:
    """保存当前请求上下文中的会话 ID。"""
    _session_id_ctx.set(session_id)


def get_current_session_id() -> Optional[str]:
    """获取当前请求上下文中的会话 ID。"""
    return _session_id_ctx.get()
