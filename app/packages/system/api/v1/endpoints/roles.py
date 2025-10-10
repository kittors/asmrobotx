"""角色管理相关的路由定义。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.roles import (
    RoleCreateRequest,
    RoleDeletionResponse,
    RoleDetailResponse,
    RoleListResponse,
    RoleMutationResponse,
    RoleUpdateRequest,
    RoleStatusUpdateRequest,
    RoleAssignedUsersResponse,
    RoleAssignedOrganizationsResponse,
    RoleAssignUsersRequest,
    RoleAssignOrganizationsRequest,
)
from app.packages.system.core.constants import HTTP_STATUS_BAD_REQUEST
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.exceptions import AppException
from app.packages.system.core.logger import logger
from app.packages.system.core.timezone import get_timezone, now as tz_now
from app.packages.system.models.user import User
from app.packages.system.services.log_service import log_service
from app.packages.system.services.role_service import role_service

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=RoleListResponse)
def list_roles(
    name: Optional[str] = Query(None, description="角色名称模糊匹配"),
    role_key: Optional[str] = Query(None, description="权限字符模糊匹配"),
    statuses: Optional[list[str]] = Query(None, description="角色状态，可多选"),
    start_time: Optional[str] = Query(None, description="开始时间，格式: YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式: YYYY-MM-DD HH:MM:SS"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> RoleListResponse:
    return role_service.list_roles(
        db,
        name=name,
        role_key=role_key,
        statuses=_normalize_sequence(statuses),
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        page=page,
        page_size=page_size,
    )


@router.get("/export")
def export_roles(
    request: Request,
    name: Optional[str] = Query(None),
    role_key: Optional[str] = Query(None),
    statuses: Optional[list[str]] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_headers: Optional[dict[str, Any]] = None

    try:
        response = role_service.export(
            db,
            name=name,
            role_key=role_key,
            statuses=_normalize_sequence(statuses),
            start_time=_parse_datetime(start_time),
            end_time=_parse_datetime(end_time),
        )
        response_headers = {
            "content_type": response.media_type,
            "content_disposition": response.headers.get("Content-Disposition"),
        }
        return response
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="export",
            class_method="app.packages.system.api.v1.endpoints.roles.export_roles",
            request_body={
                "name": name,
                "role_key": role_key,
                "statuses": statuses,
                "start_time": start_time,
                "end_time": end_time,
            },
            response_body=response_headers,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/{role_id}", response_model=RoleDetailResponse)
def get_role_detail(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> RoleDetailResponse:
    return role_service.get_detail(db, role_id=role_id)


@router.post("", response_model=RoleMutationResponse)
def create_role(
    payload: RoleCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RoleMutationResponse:
    body = payload.model_dump()
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = role_service.create(
            db,
            name=body["name"],
            role_key=body["role_key"],
            sort_order=body.get("sort_order", 0),
            status=body.get("status"),
            remark=body.get("remark"),
            permission_ids=body.get("permission_ids"),
        )
        return response_payload
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="create",
            class_method="app.packages.system.api.v1.endpoints.roles.create_role",
            request_body=body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.put("/{role_id}", response_model=RoleMutationResponse)
def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RoleMutationResponse:
    body = payload.model_dump()
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    audit_body = {"role_id": role_id, **body}

    try:
        response_payload = role_service.update(
            db,
            role_id=role_id,
            name=body["name"],
            role_key=body["role_key"],
            sort_order=body.get("sort_order", 0),
            status=body.get("status"),
            remark=body.get("remark"),
            permission_ids=body.get("permission_ids"),
        )
        return response_payload
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.roles.update_role",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.delete("/{role_id}", response_model=RoleDeletionResponse)
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RoleDeletionResponse:
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = role_service.delete(db, role_id=role_id)
        return response_payload
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="delete",
            class_method="app.packages.system.api.v1.endpoints.roles.delete_role",
            request_body={"role_id": role_id},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.patch("/{role_id}/status", response_model=RoleMutationResponse)
def change_role_status(
    role_id: int,
    payload: RoleStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RoleMutationResponse:
    body = payload.model_dump()
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    audit_body = {"role_id": role_id, **body}

    try:
        response_payload = role_service.change_status(db, role_id=role_id, status=body["status"])
        return response_payload
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.roles.change_role_status",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/{role_id}/users", response_model=RoleAssignedUsersResponse)
def get_role_assigned_users(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> RoleAssignedUsersResponse:
    return role_service.get_assigned_user_ids(db, role_id=role_id)


@router.put("/{role_id}/users", response_model=RoleAssignedUsersResponse)
def assign_role_users(
    role_id: int,
    payload: RoleAssignUsersRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RoleAssignedUsersResponse:
    body = payload.model_dump()
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    audit_body = {"role_id": role_id, **body}

    try:
        response_payload = role_service.assign_users(db, role_id=role_id, user_ids=body.get("user_ids", []))
        return response_payload
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.roles.assign_role_users",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/{role_id}/organizations", response_model=RoleAssignedOrganizationsResponse)
def get_role_assigned_organizations(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> RoleAssignedOrganizationsResponse:
    return role_service.get_assigned_organization_ids(db, role_id=role_id)


@router.put("/{role_id}/organizations", response_model=RoleAssignedOrganizationsResponse)
def assign_role_organizations(
    role_id: int,
    payload: RoleAssignOrganizationsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RoleAssignedOrganizationsResponse:
    body = payload.model_dump()
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    audit_body = {"role_id": role_id, **body}

    try:
        response_payload = role_service.assign_organizations(
            db, role_id=role_id, organization_ids=body.get("organization_ids", [])
        )
        return response_payload
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.roles.assign_role_organizations",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    token = value.strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(token, pattern)
            return parsed.replace(tzinfo=get_timezone())
        except ValueError:
            continue
    raise AppException(msg="时间格式不正确，应为 YYYY-MM-DD HH:MM:SS", code=HTTP_STATUS_BAD_REQUEST)


def _normalize_sequence(values: Optional[Iterable[str]]) -> Optional[list[str]]:
    if not values:
        return None
    normalized = [item for item in (value.strip() for value in values) if item]
    return normalized or None


def _record_operation_log(
    *,
    db: Session,
    request: Request,
    current_user: User,
    business_type: str,
    class_method: str,
    request_body: Optional[dict[str, Any]],
    response_body: Optional[dict[str, Any]],
    status: str,
    error_message: Optional[str],
    started_at: datetime,
) -> None:
    """记录角色管理相关操作日志。"""

    finished_at = tz_now()
    cost_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
    status_value = status if status in {"success", "failure"} else "other"

    try:
        log_service.record_operation_log(
            db,
            payload={
                "module": "角色管理",
                "business_type": business_type,
                "operator_name": current_user.username,
                "operator_department": None,
                "operator_ip": _extract_client_ip(request),
                "operator_location": None,
                "request_method": request.method,
                "request_uri": _build_request_uri(request),
                "class_method": class_method,
                "request_params": _safe_json_dump(request_body),
                "response_params": _safe_json_dump(response_body),
                "status": status_value,
                "error_message": error_message,
                "cost_ms": cost_ms,
                "operate_time": finished_at,
            },
        )
    except Exception as exc:  # pragma: no cover - 防御性记录
        logger.warning("Failed to record role operation log: %s", exc)


def _extract_client_ip(request: Request) -> Optional[str]:
    for header in ("x-forwarded-for", "x-real-ip", "x-client-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _safe_json_dump(payload: Optional[dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to serialize role log payload: %s", exc)
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path
