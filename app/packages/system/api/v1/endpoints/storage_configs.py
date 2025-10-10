"""存储源配置相关路由。

为与操作日志监听规则对齐，针对变更类接口（新增/更新/删除/连通性测试）补充操作日志记录。
查询类接口保持简洁，暂不记录以避免日志噪音。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.storage import (
    StorageConfigCreate,
    StorageConfigListResponse,
    StorageConfigMutationResponse,
    StorageConfigUpdate,
    StorageTestResponse,
)
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.logger import logger
from app.packages.system.core.timezone import now as tz_now
from app.packages.system.models.user import User
from app.packages.system.services.log_service import log_service
from app.packages.system.services.storage_service import storage_service

router = APIRouter(prefix="/storage-configs", tags=["storage-configs"])


@router.get("", response_model=StorageConfigListResponse)
def list_configs(db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.list_configs(db)


@router.get("/{config_id}", response_model=StorageConfigMutationResponse)
def get_config(config_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.get_config(db, id=config_id)


@router.post("", response_model=StorageConfigMutationResponse)
def create_config(
    request: Request,
    payload: StorageConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump()

    try:
        response_payload = storage_service.create_config(db, body)
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
            class_method="app.packages.system.api.v1.endpoints.storage_configs.create_config",
            request_body=body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.put("/{config_id}", response_model=StorageConfigMutationResponse)
def update_config(
    request: Request,
    payload: StorageConfigUpdate,
    config_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump(exclude_unset=True)

    try:
        response_payload = storage_service.update_config(db, id=config_id, payload=body)
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
            class_method="app.packages.system.api.v1.endpoints.storage_configs.update_config",
            request_body={"config_id": config_id, **body},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.delete("/{config_id}", response_model=StorageConfigMutationResponse)
def delete_config(
    request: Request,
    config_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = storage_service.delete_config(db, id=config_id)
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
            class_method="app.packages.system.api.v1.endpoints.storage_configs.delete_config",
            request_body={"config_id": config_id},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/test", response_model=StorageTestResponse)
def test_config(
    request: Request,
    payload: StorageConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump()

    try:
        response_payload = storage_service.test_connection(db, body)
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
            class_method="app.packages.system.api.v1.endpoints.storage_configs.test_config",
            request_body=body,
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
    """记录存储配置相关的操作日志。"""

    finished_at = tz_now()
    cost_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
    status_value = status if status in {"success", "failure"} else "other"

    try:
        log_service.record_operation_log(
            db,
            payload={
                "module": "存储管理",
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
        logger.warning("Failed to record storage config operation log: %s", exc)


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
    except Exception:
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path
