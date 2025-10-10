"""组织 + 角色 数据域全局中间件。

说明：
- 在每个请求开始时解析 Authorization 头部（若存在），解析 JWT，加载用户的组织与角色；
- 将 {organization_id, role_ids, user_id, is_admin} 写入数据域上下文；
- 无鉴权/无效 token 时，写入空数据域以保持幂等；
- 实际的权限校验依然由路由的依赖（get_current_user）完成；本中间件仅提供“数据域”用途。
"""

from __future__ import annotations

from typing import Callable, Awaitable, Optional

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.datascope import set_scope
from app.packages.system.core.constants import ADMIN_ROLE, ACCESS_TOKEN_TYPE
from app.packages.system.core.security import decode_token
from app.packages.system.db.session import SessionLocal
from app.packages.system.models.user import User


class DataScopeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # pragma: no cover - middleware glue
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # 默认空数据域
        set_scope(organization_id=None, role_ids=(), user_id=None, is_admin=False)

        try:
            # 解析 Authorization: Bearer <token>
            headers = dict((k.decode().lower(), v.decode()) for k, v in scope.get("headers", []))
            auth = headers.get("authorization")
            if not auth:
                await self.app(scope, receive, send)
                return
            parts = auth.split()
            if len(parts) != 2 or parts[0].lower() != ACCESS_TOKEN_TYPE:
                await self.app(scope, receive, send)
                return
            token = parts[1]
            payload = decode_token(token)
            if not payload:
                await self.app(scope, receive, send)
                return

            user_id = payload.get("user_id")
            if not user_id:
                await self.app(scope, receive, send)
                return

            # 查询用户组织与角色集合
            db = SessionLocal()
            try:
                # Python 3.9 兼容：使用 Optional[User] 而非 `User | None`
                user: Optional[User] = db.query(User).filter(
                    User.id == int(user_id), User.is_deleted.is_(False)
                ).first()
                if user is None:
                    await self.app(scope, receive, send)
                    return
                role_ids = tuple(sorted(role.id for role in user.roles))
                is_admin = any(
                    (
                        ((getattr(role, "role_key", "") or "").lower() == ADMIN_ROLE)
                        or ((role.name or "").lower() == ADMIN_ROLE)
                    )
                    and ((getattr(role, "status", "normal") or "normal").lower() == "normal")
                    for role in user.roles
                )
                set_scope(
                    organization_id=user.organization_id,
                    role_ids=role_ids,
                    user_id=user.id,
                    is_admin=is_admin,
                )
            finally:
                db.close()
        except Exception:
            # 防御性：任何异常都不应影响主流程
            pass

        await self.app(scope, receive, send)
