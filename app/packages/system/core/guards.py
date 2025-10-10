"""统一的管理员/系统保留对象保护封装。

集中维护关于“管理员用户/管理员角色”的判定与拦截逻辑，避免到处散落硬编码，便于后期统一调整。
"""

from __future__ import annotations

from typing import Optional

from app.packages.system.core.constants import (
    ADMIN_ROLE,
    DEFAULT_ADMIN_USERNAME,
    HTTP_STATUS_FORBIDDEN,
)
from app.packages.system.core.exceptions import AppException


def is_admin_role_tokens(name: Optional[str], role_key: Optional[str]) -> bool:
    n = (name or "").strip().lower()
    k = (role_key or "").strip().lower()
    return n == ADMIN_ROLE or k == ADMIN_ROLE


def is_admin_role(role: object) -> bool:
    name = getattr(role, "name", None)
    key = getattr(role, "role_key", None)
    return is_admin_role_tokens(name, key)


def is_admin_username(username: Optional[str]) -> bool:
    return (username or "").strip().lower() == DEFAULT_ADMIN_USERNAME


def is_admin_user(user: object) -> bool:
    return is_admin_username(getattr(user, "username", None))


def forbid_if_admin_role_tokens(name: Optional[str], role_key: Optional[str], *, message: str) -> None:
    if is_admin_role_tokens(name, role_key):
        raise AppException(message, HTTP_STATUS_FORBIDDEN)


def forbid_if_admin_role(role: object, *, message: str) -> None:
    if is_admin_role(role):
        raise AppException(message, HTTP_STATUS_FORBIDDEN)


def forbid_if_admin_user(user: object, *, message: str) -> None:
    if is_admin_user(user):
        raise AppException(message, HTTP_STATUS_FORBIDDEN)

