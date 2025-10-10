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
from app.packages.system.crud.roles import role_crud
from app.packages.system.models.role import Role
from app.packages.system.core.datascope import get_scope


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
        # 归属组织与创建人（若上下文可用）
        if hasattr(role, "organization_id") and scope.organization_id is not None:
            role.organization_id = scope.organization_id
        if hasattr(role, "created_by") and scope.user_id is not None:
            role.created_by = scope.user_id
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
        if role.name in {ADMIN_ROLE, DEFAULT_USER_ROLE}:
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
        role.status = normalized_status
        db.add(role)
        db.commit()
        db.refresh(role)
        data = self._serialize_role_detail(role)
        return create_response("更新角色状态成功", data, HTTP_STATUS_OK)

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
