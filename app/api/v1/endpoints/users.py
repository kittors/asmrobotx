"""用户相关路由定义。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.schemas.users import (
    UserCreateRequest,
    UserDeletionResponse,
    UserImportResponse,
    UserInfoResponse,
    UserListResponse,
    UserMutationResponse,
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserUpdateRequest,
)
from app.core.constants import HTTP_STATUS_BAD_REQUEST
from app.core.dependencies import get_current_active_user, get_db
from app.core.exceptions import AppException
from app.core.logger import logger
from app.models.user import User
from app.services.log_service import log_service
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserInfoResponse)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> UserInfoResponse:
    """返回当前已认证且激活用户的概要信息。"""
    return user_service.build_user_profile(current_user)


@router.get("", response_model=UserListResponse)
def list_users(
    username: Optional[str] = Query(None, description="用户名模糊匹配"),
    statuses: Optional[list[str]] = Query(None, description="用户状态，可多选"),
    start_time: Optional[str] = Query(None, description="开始时间，格式: YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式: YYYY-MM-DD HH:MM:SS"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> UserListResponse:
    return user_service.list_users(
        db,
        username=username,
        statuses=_normalize_sequence(statuses),
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        page=page,
        page_size=page_size,
    )


@router.get("/export")
def export_users(
    request: Request,
    username: Optional[str] = Query(None),
    statuses: Optional[list[str]] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_headers: Optional[dict[str, Any]] = None

    try:
        response = user_service.export_users(
            db,
            username=username,
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
            class_method="app.api.v1.endpoints.users.export_users",
            request_body={
                "username": username,
                "statuses": statuses,
                "start_time": start_time,
                "end_time": end_time,
            },
            response_body=response_headers,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/template")
def download_template(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None

    try:
        return user_service.download_template()
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
            class_method="app.api.v1.endpoints.users.download_template",
            request_body=None,
            response_body={"template": "user-template.xlsx"},
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/import", response_model=UserImportResponse)
def import_users(
    request: Request,
    file: UploadFile = File(..., description="用户导入文件，支持 xlsx"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserImportResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = user_service.import_users(db, file=file)
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
            business_type="import",
            class_method="app.api.v1.endpoints.users.import_users",
            request_body={"filename": file.filename},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("", response_model=UserMutationResponse)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserMutationResponse:
    body = payload.model_dump()
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = user_service.create_user(
            db,
            username=body["username"],
            password=body["password"],
            nickname=body.get("nickname"),
            status=body.get("status"),
            role_ids=body.get("role_ids"),
            remark=body.get("remark"),
            organization_id=body.get("organization_id"),
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
            class_method="app.api.v1.endpoints.users.create_user",
            request_body=body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.put("/{user_id}", response_model=UserMutationResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserMutationResponse:
    body = payload.model_dump(exclude_unset=True)
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    audit_body = {"user_id": user_id, **body}

    try:
        response_payload = user_service.update_user(
            db,
            user_id=user_id,
            nickname=body.get("nickname"),
            status=body.get("status"),
            role_ids=body.get("role_ids"),
            remark=body.get("remark"),
            organization_id=body.get("organization_id"),
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
            class_method="app.api.v1.endpoints.users.update_user",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.delete("/{user_id}", response_model=UserDeletionResponse)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserDeletionResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = user_service.delete_user(db, user_id=user_id)
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
            class_method="app.api.v1.endpoints.users.delete_user",
            request_body={"user_id": user_id},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.put("/{user_id}/reset-password", response_model=UserPasswordResetResponse)
def reset_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserPasswordResetResponse:
    body = payload.model_dump()
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = user_service.reset_password(
            db,
            user_id=user_id,
            new_password=body["password"],
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
            class_method="app.api.v1.endpoints.users.reset_password",
            request_body={"user_id": user_id},
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
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise AppException("时间格式不正确，应为 YYYY-MM-DD HH:MM:SS", HTTP_STATUS_BAD_REQUEST)


def _normalize_sequence(values: Optional[Iterable[str]]) -> Optional[list[str]]:
    if not values:
        return None
    normalized = [item for item in (value.strip() for value in values if value) if item]
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
    finished_at = datetime.now(timezone.utc)
    cost_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
    status_value = status if status in {"success", "failure"} else "other"

    try:
        log_service.record_operation_log(
            db,
            payload={
                "module": "用户管理",
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
        logger.warning("Failed to record user operation log: %s", exc)


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
        logger.debug("Failed to serialize user log payload: %s", exc)
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path
