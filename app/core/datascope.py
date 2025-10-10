"""全局数据域上下文与通用查询助手（组织 + 角色）。

职责：
- 维护一个 per-request 的数据域上下文（organization_id, role_ids, user_id 可选）；
- 在通用 CRUD 查询中追加组织与角色过滤；
- 在创建时补全 created_by / organization_id 默认值（强制非空）。

说明：
- 数据隔离基于“组织 + 角色”，不以用户维度做数据隔离；
- created_by 仅作为审计字段存在，不用于过滤；
- 模型若未声明“角色归属字段”（如 owner_role_id），则忽略角色过滤，仅按组织过滤；
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Query


@dataclass
class DataScope:
    organization_id: Optional[int]
    role_ids: tuple[int, ...]
    user_id: Optional[int] = None  # 审计用，不做数据隔离
    is_admin: bool = False
    # 是否启用数据隔离（组织/角色）
    isolation_enabled: bool = True


_scope_ctx: ContextVar[DataScope] = ContextVar(
    "data_scope",
    default=DataScope(organization_id=None, role_ids=(), user_id=None, is_admin=False, isolation_enabled=True),
)


def set_scope(*, organization_id: Optional[int], role_ids: list[int] | tuple[int, ...], user_id: Optional[int] = None, is_admin: bool = False, isolation_enabled: bool = True) -> None:
    _scope_ctx.set(
        DataScope(
            organization_id=organization_id,
            role_ids=tuple(int(x) for x in (role_ids or ())),
            user_id=user_id,
            is_admin=is_admin,
            isolation_enabled=isolation_enabled,
        )
    )


def get_scope() -> DataScope:
    return _scope_ctx.get()


def apply_data_scope(query: Query, model: Any) -> Query:
    """按“组织 + 角色”追加过滤（若模型存在对应字段）。

    - 组织：若模型包含 organization_id，则按当前组织过滤；
    - 角色：若模型包含 owner_role_id/role_id 字段之一，则按当前角色集合过滤；
    - 若当前请求未带组织/角色信息，则不追加对应过滤。
    """
    scope = get_scope()

    # 全局关闭（例如通过路由策略关闭）或管理员：不追加任何数据域过滤
    if not getattr(scope, "isolation_enabled", True):
        return query

    # 管理员跨组织/角色查看数据：若当前用户具备 admin 角色，则不做任何数据域过滤。
    # 说明：这与业务侧“管理员拥有全部权限”的预期一致，也能修复登录 admin
    # 时菜单/路由为空（因组织不匹配被过滤掉）的现象。
    if getattr(scope, "is_admin", False):  # 防御性：scope 可能被替换为简化对象
        return query

    if hasattr(model, "organization_id") and scope.organization_id is not None:
        try:
            org_col = getattr(model, "organization_id")
            query = query.filter((org_col == scope.organization_id) | (org_col.is_(None)))
        except Exception:
            pass

    # 可选的“角色维度”过滤：仅当模型声明了单角色归属字段时生效
    role_col_name = None
    for candidate in ("owner_role_id", "role_id"):
        if hasattr(model, candidate):
            role_col_name = candidate
            break
    if role_col_name and scope.role_ids:
        try:
            query = query.filter(getattr(model, role_col_name).in_(scope.role_ids))
        except Exception:
            pass

    return query


def scope_defaults_for_create(model: Any) -> dict[str, Any]:
    """为创建操作提供 created_by 与 organization_id 的默认值。"""
    scope = get_scope()
    payload: dict[str, Any] = {}
    if hasattr(model, "created_by") and scope.user_id is not None:
        payload["created_by"] = scope.user_id
    if hasattr(model, "organization_id") and scope.organization_id is not None:
        payload["organization_id"] = scope.organization_id
    # 可选：若模型有 owner_role_id 且当前只有单一角色，可作为默认归属角色
    if hasattr(model, "owner_role_id") and len(scope.role_ids) == 1:
        payload["owner_role_id"] = scope.role_ids[0]
    return payload
