"""数据域上下文与查询助手。

目标：
- 将当前请求的 `user_id` 与 `organization_id` 注入到上下文；
- 在 CRUD 层统一施加“按组织隔离”的查询过滤；
- 在创建对象时，自动补全 `created_by` 与 `organization_id`（若模型支持且未显式传入）。

说明：
- 管理员（admin）默认不做特殊放行，这样各自组织的数据天然隔离；
  如需放开，可自行扩展 `is_admin` 的判定并在 `apply_data_scope` 里跳过过滤。
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Query


@dataclass
class DataScope:
    user_id: Optional[int]
    organization_id: Optional[int]
    is_admin: bool = False


_scope_ctx: ContextVar[DataScope] = ContextVar(
    "data_scope", default=DataScope(user_id=None, organization_id=None, is_admin=False)
)


def set_scope(*, user_id: Optional[int], organization_id: Optional[int], is_admin: bool = False) -> None:
    """设置当前请求的数据域。"""
    _scope_ctx.set(DataScope(user_id=user_id, organization_id=organization_id, is_admin=is_admin))


def get_scope() -> DataScope:
    """获取当前请求的数据域（若未设置，返回空域）。"""
    return _scope_ctx.get()


def apply_data_scope(query: Query, model: Any) -> Query:
    """对传入查询按组织维度加过滤（当模型包含 `organization_id` 字段时）。"""
    scope = get_scope()
    org_id = scope.organization_id
    if org_id is None:
        return query
    # 仅当模型定义了 organization_id 字段时才施加过滤
    if hasattr(model, "organization_id"):
        try:
            org_col = getattr(model, "organization_id")
            # 包含“全局记录”（organization_id IS NULL），以兼容系统级配置数据
            return query.filter((org_col == org_id) | (org_col.is_(None)))
        except Exception:
            # 防御性：任何异常都不应破坏原查询
            return query
    return query


def scope_defaults_for_create(model: Any) -> dict[str, Any]:
    """为创建操作提供默认的 `created_by` 与 `organization_id` 字段值。"""
    scope = get_scope()
    payload: dict[str, Any] = {}
    if hasattr(model, "created_by") and scope.user_id is not None:
        payload["created_by"] = scope.user_id
    if hasattr(model, "organization_id") and scope.organization_id is not None:
        payload["organization_id"] = scope.organization_id
    return payload
