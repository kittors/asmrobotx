"""访问控制管理相关的路由定义。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.access_control import (
    AccessControlCreateRequest,
    AccessControlDeletionResponse,
    AccessControlDetailResponse,
    AccessControlMutationResponse,
    AccessControlTreeResponse,
    AccessControlUpdateRequest,
    RouterListResponse,
)
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.logger import logger
from app.packages.system.models.user import User
from app.packages.system.services.access_control_service import access_control_service
from app.packages.system.services.log_service import log_service

router = APIRouter(prefix="/access-controls", tags=["access_controls"])


@router.get("", response_model=AccessControlTreeResponse)
def list_access_controls(
    name: Optional[str] = None,
    enabled_status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> AccessControlTreeResponse:
    """按照查询条件返回访问控制树形结构。"""
    return access_control_service.list_tree(db, name=name, enabled_status=enabled_status)


@router.get("/routers", response_model=RouterListResponse)
def get_routers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RouterListResponse:
    """返回前端动态路由配置，并记录查询操作日志。"""

    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = access_control_service.get_routers(db)
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
            business_type="query",
            class_method="app.packages.system.api.v1.endpoints.access_controls.get_routers",
            request_body=None,
            response_body=response_payload if isinstance(response_payload, dict) else None,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/{item_id}", response_model=AccessControlDetailResponse)
def get_access_control_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> AccessControlDetailResponse:
    """获取指定访问控制项的详细信息。"""
    return access_control_service.get_detail(db, item_id=item_id)


@router.post("", response_model=AccessControlMutationResponse)
def create_access_control_item(
    payload: AccessControlCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AccessControlMutationResponse:
    """创建新的访问控制节点。"""

    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump(exclude_none=True)

    try:
        response_payload = access_control_service.create(db, payload=body)
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
            class_method="app.packages.system.api.v1.endpoints.access_controls.create_access_control_item",
            request_body=body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.put("/{item_id}", response_model=AccessControlMutationResponse)
def update_access_control_item(
    item_id: int,
    payload: AccessControlUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AccessControlMutationResponse:
    """更新现有访问控制节点。"""

    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump(exclude_unset=True)
    audit_body = {"item_id": item_id, **body}

    try:
        response_payload = access_control_service.update(db, item_id=item_id, payload=body)
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
            class_method="app.packages.system.api.v1.endpoints.access_controls.update_access_control_item",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.delete("/{item_id}", response_model=AccessControlDeletionResponse)
def delete_access_control_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AccessControlDeletionResponse:
    """删除指定的访问控制节点。"""

    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = access_control_service.delete(db, item_id=item_id)
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
            class_method="app.packages.system.api.v1.endpoints.access_controls.delete_access_control_item",
            request_body={"item_id": item_id},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


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
    """记录访问控制相关的操作日志。"""

    finished_at = datetime.now(timezone.utc)
    cost_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)

    status_value = status if status in {"success", "failure"} else "other"

    try:
        log_service.record_operation_log(
            db,
            payload={
                "module": "访问控制管理",
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
    except Exception as exc:  # pragma: no cover - 日志失败不应阻断业务流程
        logger.warning("Failed to record operation log: %s", exc)


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
    except Exception as exc:  # pragma: no cover - 防御性处理
        logger.debug("Failed to serialize payload for log: %s", exc)
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path
