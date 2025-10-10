"""角色管理服务：封装角色的增删改查与导出逻辑。"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable, Optional

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.packages.system.core.constants import (
    ADMIN_ROLE,
    DEFAULT_USER_ROLE,
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_CONFLICT,
    HTTP_STATUS_FORBIDDEN,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from app.packages.system.core.enums import RoleStatusEnum
from app.packages.system.core.exceptions import AppException
from app.packages.system.core.responses import create_response
from app.packages.system.core.timezone import format_datetime
from app.packages.system.crud.access_control import access_control_crud
from app.packages.system.crud.users import user_crud
from app.packages.system.crud.organizations import organization_crud
from app.packages.system.crud.roles import role_crud
from app.packages.system.models.role import Role
from app.core.datascope import get_scope
from app.packages.system.core.constants import DEFAULT_ORGANIZATION_NAME
from app.packages.system.models.organization import Organization
from app.packages.system.core.guards import (
    forbid_if_admin_role,
    forbid_if_admin_role_tokens,
    is_admin_role,
)


class RoleService:
    """聚合角色管理相关的业务能力。"""

    _STATUS_LABELS = {
        RoleStatusEnum.NORMAL.value: "正常",
        RoleStatusEnum.DISABLED.value: "停用",
    }

    def list_roles(
        self,
        db: Session,
        *,
        name: Optional[str] = None,
        role_key: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        page = max(page, 1)
        page_size = max(page_size, 1)
        normalized_statuses = self._normalize_statuses(statuses)

        items, total = role_crud.list_with_filters(
            db,
            name=name,
            role_key=role_key,
            statuses=normalized_statuses,
            start_time=start_time,
            end_time=end_time,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

        payload = {
            "total": total,
            "items": [self._serialize_role_summary(item) for item in items],
            "page": page,
            "page_size": page_size,
        }
        return create_response("获取角色列表成功", payload, HTTP_STATUS_OK)

    def get_detail(self, db: Session, *, role_id: int) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        data = self._serialize_role_detail(role)
        return create_response("获取角色详情成功", data, HTTP_STATUS_OK)

    def create(
        self,
        db: Session,
        *,
        name: str,
        role_key: str,
        sort_order: int = 0,
        status: str = RoleStatusEnum.NORMAL.value,
        remark: Optional[str] = None,
        permission_ids: Optional[Iterable[int]] = None,
    ) -> dict:
        # 禁止创建名称或权限字符为 admin 的角色（系统保留）
        forbid_if_admin_role_tokens(name, role_key, message="不允许创建系统保留角色（admin）")

        self._assert_unique_constraints(db, name=name, role_key=role_key)
        normalized_status = self._normalize_status(status)
        permissions = self._load_access_controls(db, permission_ids)

        scope = get_scope()
        role = Role(
            name=name.strip(),
            role_key=role_key.strip(),
            sort_order=max(sort_order, 0),
            status=normalized_status,
            remark=(remark.strip() if remark and remark.strip() else None),
        )
        # 归属组织与创建人（若上下文可用，否则兜底 admin/默认组织）
        if hasattr(role, "organization_id"):
            if scope.organization_id is not None:
                role.organization_id = scope.organization_id
            else:
                row = db.query(Organization.id).filter(Organization.name == DEFAULT_ORGANIZATION_NAME).first()
                if row is None:
                    raise AppException("默认组织不存在", HTTP_STATUS_BAD_REQUEST)
                role.organization_id = row[0] if not isinstance(row, Organization) else row.id
        if hasattr(role, "created_by"):
            role.created_by = scope.user_id if scope.user_id is not None else 1
        role.access_controls = permissions
        db.add(role)
        db.commit()
        db.refresh(role)

        data = self._serialize_role_detail(role)
        return create_response("创建角色成功", data, HTTP_STATUS_OK)

    def update(
        self,
        db: Session,
        *,
        role_id: int,
        name: str,
        role_key: str,
        sort_order: int,
        status: str,
        remark: Optional[str],
        permission_ids: Optional[Iterable[int]],
    ) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)

        self._assert_unique_constraints(db, name=name, role_key=role_key, exclude_id=role_id)

        normalized_status = self._normalize_status(status)
        permissions = self._load_access_controls(db, permission_ids)

        role.name = name.strip()
        role.role_key = role_key.strip()
        role.sort_order = max(sort_order, 0)
        role.status = normalized_status
        role.remark = remark.strip() if remark and remark.strip() else None
        role.access_controls = permissions

        db.add(role)
        db.commit()
        db.refresh(role)

        data = self._serialize_role_detail(role)
        return create_response("更新角色成功", data, HTTP_STATUS_OK)

    def delete(self, db: Session, *, role_id: int) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        # 禁止删除系统内置角色：名称为 admin/user 或权限字符为 admin
        if (role.name or "").strip().lower() in {ADMIN_ROLE, DEFAULT_USER_ROLE} or (role.role_key or "").strip().lower() == ADMIN_ROLE:
            raise AppException("系统内置角色不允许删除", HTTP_STATUS_FORBIDDEN)
        if role.users:
            raise AppException("存在关联用户，无法删除该角色", HTTP_STATUS_BAD_REQUEST)

        role_crud.soft_delete(db, role)
        return create_response("删除角色成功", {"role_id": role_id}, HTTP_STATUS_OK)

    def change_status(self, db: Session, *, role_id: int, status: str) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)

        normalized_status = self._normalize_status(status)
        # 管理员角色禁止停用（按名称/权限字符判断，大小写不敏感）
        if is_admin_role(role) and normalized_status == RoleStatusEnum.DISABLED.value:
            raise AppException("管理员角色不允许停用", HTTP_STATUS_FORBIDDEN)
        role.status = normalized_status
        db.add(role)
        db.commit()
        db.refresh(role)
        data = self._serialize_role_detail(role)
        return create_response("更新角色状态成功", data, HTTP_STATUS_OK)

    def get_assigned_organization_ids(self, db: Session, *, role_id: int) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        # 管理员角色：数据权限默认为“全部组织”
        if is_admin_role(role):
            ids = [org.id for org in organization_crud.list_all(db)]
            payload = {"role_id": role.id, "organization_ids": ids}
            return create_response("获取角色数据权限成功", payload, HTTP_STATUS_OK)
        # 非管理员：按已分配组织返回
        org_ids = sorted({org.id for org in getattr(role, "organizations", [])})
        payload = {"role_id": role.id, "organization_ids": org_ids}
        return create_response("获取角色数据权限成功", payload, HTTP_STATUS_OK)

    def export(
        self,
        db: Session,
        *,
        name: Optional[str] = None,
        role_key: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> StreamingResponse:
        normalized_statuses = self._normalize_statuses(statuses)
        items, _ = role_crud.list_with_filters(
            db,
            name=name,
            role_key=role_key,
            statuses=normalized_statuses,
            start_time=start_time,
            end_time=end_time,
            skip=0,
            limit=10_000,
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "角色列表"
        sheet.append(["角色名称", "权限字符", "显示顺序", "状态", "创建时间"])

        for role in items:
            sheet.append(
                [
                    role.name,
                    role.role_key,
                    role.sort_order,
                    self._STATUS_LABELS.get(role.status, role.status),
                    format_datetime(role.create_time),
                ]
            )

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"roles-{timestamp}.xlsx"
        response = StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    # -----------------------------
    # 角色分配：用户 / 组织（数据权限）
    # -----------------------------

    def get_assigned_user_ids(self, db: Session, *, role_id: int) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        user_ids = sorted({user.id for user in role.users})
        payload = {"role_id": role.id, "user_ids": user_ids}
        return create_response("获取角色已分配用户成功", payload, HTTP_STATUS_OK)

    def assign_users(self, db: Session, *, role_id: int, user_ids: Iterable[int]) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        # 去重、过滤非法值
        requested = []
        seen: set[int] = set()
        for item in (int(x) for x in user_ids or []):
            if item <= 0 or item in seen:
                continue
            seen.add(item)
            requested.append(item)
        # 查询存在的用户
        users = user_crud.list_by_ids(db, requested)
        missing = set(requested) - {u.id for u in users}
        if missing:
            raise AppException(
                f"部分用户不存在：{', '.join(str(i) for i in sorted(missing))}",
                HTTP_STATUS_NOT_FOUND,
            )
        role.users = users
        db.add(role)
        db.commit()
        db.refresh(role)
        payload = {"role_id": role.id, "user_ids": sorted({u.id for u in role.users})}
        return create_response("分配用户成功", payload, HTTP_STATUS_OK)

    def get_assigned_organization_ids(self, db: Session, *, role_id: int) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        if is_admin_role(role):
            ids = [org.id for org in organization_crud.list_all(db)]
            payload = {"role_id": role.id, "organization_ids": ids}
            return create_response("获取角色数据权限成功", payload, HTTP_STATUS_OK)
        org_ids = sorted({org.id for org in getattr(role, "organizations", [])})
        payload = {"role_id": role.id, "organization_ids": org_ids}
        return create_response("获取角色数据权限成功", payload, HTTP_STATUS_OK)

    def assign_organizations(self, db: Session, *, role_id: int, organization_ids: Iterable[int]) -> dict:
        role = role_crud.get(db, role_id)
        if role is None:
            raise AppException("角色不存在或已删除", HTTP_STATUS_NOT_FOUND)
        # 管理员角色的数据权限不可修改（固定为全选）
        forbid_if_admin_role(role, message="管理员角色不允许修改数据权限")
        requested = []
        seen: set[int] = set()
        for item in (int(x) for x in organization_ids or []):
            if item <= 0 or item in seen:
                continue
            seen.add(item)
            requested.append(item)
        orgs = organization_crud.list_by_ids(db, requested)
        missing = set(requested) - {o.id for o in orgs}
        if missing:
            raise AppException(
                f"部分组织不存在：{', '.join(str(i) for i in sorted(missing))}",
                HTTP_STATUS_NOT_FOUND,
            )
        role.organizations = orgs
        db.add(role)
        db.commit()
        db.refresh(role)
        payload = {"role_id": role.id, "organization_ids": sorted({o.id for o in role.organizations})}
        return create_response("分配数据权限成功", payload, HTTP_STATUS_OK)

    def _normalize_statuses(self, statuses: Optional[Iterable[str]]) -> Optional[list[str]]:
        if statuses is None:
            return None
        normalized: list[str] = []
        for status in statuses:
            if not status:
                continue
            normalized.append(self._normalize_status(status))
        return normalized or None

    def _normalize_status(self, status: str) -> str:
        candidate = status.strip().lower()
        if candidate in self._STATUS_LABELS:
            return candidate
        for code, label in self._STATUS_LABELS.items():
            if candidate == label.lower():
                return code
        raise AppException("未知的角色状态", HTTP_STATUS_BAD_REQUEST)

    def _load_access_controls(
        self,
        db: Session,
        permission_ids: Optional[Iterable[int]],
    ) -> list:
        if not permission_ids:
            return []
        requested = []
        seen: set[int] = set()
        for item in permission_ids:
            if item is None or item in seen:
                continue
            seen.add(item)
            requested.append(item)
        if not requested:
            return []
        permissions = access_control_crud.list_by_ids(db, requested)
        missing = set(requested) - {item.id for item in permissions}
        if missing:
            raise AppException(
                f"部分访问权限不存在：{', '.join(str(item) for item in sorted(missing))}",
                HTTP_STATUS_NOT_FOUND,
            )
        return permissions

    def _assert_unique_constraints(
        self,
        db: Session,
        *,
        name: str,
        role_key: str,
        exclude_id: Optional[int] = None,
    ) -> None:
        existing_by_name = role_crud.get_by_name(db, name.strip())
        if existing_by_name and existing_by_name.id != exclude_id:
            raise AppException("角色名称已存在", HTTP_STATUS_CONFLICT)
        existing_by_key = role_crud.get_by_key(db, role_key.strip())
        if existing_by_key and existing_by_key.id != exclude_id:
            raise AppException("权限字符已存在", HTTP_STATUS_CONFLICT)

    def _serialize_role_summary(self, role: Role) -> dict:
        return {
            "role_id": role.id,
            "role_name": role.name,
            "role_key": role.role_key,
            "sort_order": role.sort_order,
            "status": role.status,
            "status_label": self._STATUS_LABELS.get(role.status, role.status),
            "remark": role.remark,
            "create_time": format_datetime(role.create_time),
        }

    def _serialize_role_detail(self, role: Role) -> dict:
        payload = self._serialize_role_summary(role)
        payload.update(
            {
                "update_time": format_datetime(role.update_time),
                "permission_ids": sorted(item.id for item in role.access_controls),
                "permission_codes": sorted(
                    {
                        item.permission_code
                        for item in role.access_controls
                        if item.permission_code
                    }
                ),
            }
        )
        return payload


role_service = RoleService()
