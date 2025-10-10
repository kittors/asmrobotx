"""认证服务：封装注册、登录等核心业务流程。"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.packages.system.core.constants import (
    ACCESS_TOKEN_TYPE,
    DEFAULT_USER_ROLE,
    HTTP_STATUS_CONFLICT,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
    HTTP_STATUS_UNAUTHORIZED,
)
from app.packages.system.core.exceptions import AppException
from app.packages.system.core.logger import logger
from app.packages.system.core.responses import create_response
from app.packages.system.core.timezone import now as tz_now
from app.packages.system.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    store_refreshed_token,
)
from app.packages.system.crud.organizations import organization_crud
from app.packages.system.crud.roles import role_crud
from app.packages.system.crud.users import user_crud
from app.packages.system.core.enums import RoleEnum, RoleStatusEnum
from app.packages.system.models.role import Role
from app.packages.system.models.user import User
from app.packages.system.services.log_service import log_service
from app.packages.system.core.session import create_session, delete_session
from app.packages.system.core.config import get_settings


class AuthService:
    """负责处理用户注册与登录流程，并保持逻辑聚合。"""

    def register_user(self, db: Session, *, username: str, password: str, organization_id: int) -> dict:
        """创建新用户并设置默认角色，会校验用户名、组织合法性等条件。"""
        existing_user = user_crud.get_by_username(db, username)
        if existing_user:
            raise AppException(msg="用户名已存在", code=HTTP_STATUS_CONFLICT)

        organization = organization_crud.get(db, organization_id)
        if organization is None:
            raise AppException(msg="组织机构不存在", code=HTTP_STATUS_NOT_FOUND)

        default_role = role_crud.get_by_name(db, DEFAULT_USER_ROLE)
        if default_role is None:
            default_role = self._create_default_role(db)
        else:
            if not getattr(default_role, "role_key", None):
                default_role.role_key = RoleEnum.USER.value
            if not getattr(default_role, "status", None):
                default_role.status = RoleStatusEnum.NORMAL.value
            db.add(default_role)
            db.flush()

        hashed_password = get_password_hash(password)
        user = user_crud.create_with_roles(
            db,
            username=username,
            hashed_password=hashed_password,
            organization_id=organization_id,
            roles=[default_role],
        )

        user_data = {
            "user_id": user.id,
            "username": user.username,
            "organization": {
                "org_id": organization.id,
                "org_name": organization.name,
            },
            "roles": [role.name for role in user.roles],
        }
        return create_response("注册成功", user_data, HTTP_STATUS_OK)

    def login(
        self,
        db: Session,
        *,
        username: str,
        password: str,
        client_meta: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """校验用户凭证，签发访问令牌并记录登录日志。"""

        audit_meta = client_meta or {}
        user = user_crud.get_by_username(db, username)
        if user is None or not verify_password(password, user.hashed_password):
            self._record_login_log(
                db,
                username=username,
                status="failure",
                message="用户名或密码错误",
                audit_meta=audit_meta,
            )
            raise AppException(msg="用户名或密码错误", code=HTTP_STATUS_UNAUTHORIZED)

        ttl_seconds = max(get_settings().access_token_expire_minutes, 1) * 60
        session_id = create_session(user.id, ttl_seconds)

        token_payload = {"user_id": user.id, "username": user.username, "sid": session_id}
        access_token = create_access_token(token_payload)

        self._record_login_log(
            db,
            username=user.username,
            status="success",
            message="登录成功",
            audit_meta=audit_meta,
            user=user,
        )

        # 将签发的访问令牌通过上下文传递，便于响应阶段统一在 body.meta 与响应头返回
        store_refreshed_token(access_token)

        return create_response(
            "登录成功",
            {
                "access_token": access_token,
                "token_type": ACCESS_TOKEN_TYPE,
            },
            HTTP_STATUS_OK,
        )

    def _create_default_role(self, db: Session) -> Role:
        """在默认角色缺失时动态创建，确保注册流程可继续。"""
        role = Role(
            name=RoleEnum.USER.value,
            role_key=RoleEnum.USER.value,
            status=RoleStatusEnum.NORMAL.value,
            sort_order=2,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    def _record_login_log(
        self,
        db: Session,
        *,
        username: str,
        status: str,
        message: str,
        audit_meta: Dict[str, Any],
        user: Optional[User] = None,
    ) -> None:
        try:
            payload = {
                "username": username,
                "client_name": audit_meta.get("client_name") or "web",
                "device_type": audit_meta.get("device_type"),
                "ip_address": audit_meta.get("ip_address"),
                "login_location": audit_meta.get("login_location"),
                "operating_system": audit_meta.get("operating_system"),
                "browser": audit_meta.get("browser") or audit_meta.get("user_agent"),
                "status": status,
                "message": message,
                "login_time": audit_meta.get("login_time") or tz_now(),
            }

            log_service.record_login_log(db, payload=payload)
        except Exception as exc:  # pragma: no cover - 审计失败不影响登录主流程
            logger.warning("Failed to record login log for %s: %s", username, exc)
            db.rollback()


auth_service = AuthService()
