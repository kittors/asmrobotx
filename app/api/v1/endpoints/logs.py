"""日志管理相关的路由定义。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.schemas.logs import (
    LoginLogDeletionResponse,
    LoginLogListResponse,
    OperationLogDeletionResponse,
    OperationLogDetailResponse,
    OperationLogListResponse,
)
from app.core.constants import HTTP_STATUS_BAD_REQUEST
from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.services.log_service import log_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/operations", response_model=OperationLogListResponse)
def list_operation_logs(
    module: Optional[str] = Query(None, description="系统模块名称模糊匹配"),
    operator_name: Optional[str] = Query(None, description="操作人员名称模糊匹配"),
    operator_ip: Optional[str] = Query(None, description="操作地址/IP 模糊匹配"),
    operation_types: Optional[list[str]] = Query(None, description="操作类型，可多选"),
    statuses: Optional[list[str]] = Query(None, description="操作状态过滤，可多选"),
    request_uri: Optional[str] = Query(None, description="请求地址模糊匹配"),
    start_time: Optional[str] = Query(None, description="开始时间，格式: YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式: YYYY-MM-DD HH:MM:SS"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> OperationLogListResponse:
    return log_service.list_operation_logs(
        db,
        module=module,
        operator_name=operator_name,
        operator_ip=operator_ip,
        operation_types=_normalize_sequence(operation_types),
        statuses=_normalize_sequence(statuses),
        request_uri=request_uri,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        page=page,
        page_size=page_size,
    )


@router.get("/operations/export")
def export_operation_logs(
    module: Optional[str] = Query(None),
    operator_name: Optional[str] = Query(None),
    operator_ip: Optional[str] = Query(None),
    operation_types: Optional[list[str]] = Query(None),
    statuses: Optional[list[str]] = Query(None),
    request_uri: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return log_service.export_operation_logs(
        db,
        module=module,
        operator_name=operator_name,
        operator_ip=operator_ip,
        operation_types=_normalize_sequence(operation_types),
        statuses=_normalize_sequence(statuses),
        request_uri=request_uri,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
    )


@router.get("/operations/{log_number}", response_model=OperationLogDetailResponse)
def get_operation_log_detail(
    log_number: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> OperationLogDetailResponse:
    return log_service.get_operation_log_detail(db, log_number=log_number)


@router.delete("/operations/{log_number}", response_model=OperationLogDeletionResponse)
def delete_operation_log(
    log_number: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> OperationLogDeletionResponse:
    return log_service.delete_operation_log(db, log_number=log_number)


@router.delete("/operations", response_model=OperationLogDeletionResponse)
def clear_operation_logs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> OperationLogDeletionResponse:
    return log_service.clear_operation_logs(db)


@router.get("/logins", response_model=LoginLogListResponse)
def list_login_logs(
    username: Optional[str] = Query(None, description="用户名模糊匹配"),
    ip_address: Optional[str] = Query(None, description="登录 IP 模糊匹配"),
    statuses: Optional[list[str]] = Query(None, description="登录状态过滤，可多选"),
    start_time: Optional[str] = Query(None, description="开始时间，格式: YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式: YYYY-MM-DD HH:MM:SS"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LoginLogListResponse:
    return log_service.list_login_logs(
        db,
        username=username,
        ip_address=ip_address,
        statuses=_normalize_sequence(statuses),
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        page=page,
        page_size=page_size,
    )


@router.delete("/logins/{visit_number}", response_model=LoginLogDeletionResponse)
def delete_login_log(
    visit_number: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LoginLogDeletionResponse:
    return log_service.delete_login_log(db, visit_number=visit_number)


@router.delete("/logins", response_model=LoginLogDeletionResponse)
def clear_login_logs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LoginLogDeletionResponse:
    return log_service.clear_login_logs(db)


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="时间格式不正确，应为 YYYY-MM-DD HH:MM:SS")


def _normalize_sequence(values: Optional[Iterable[str]]) -> Optional[list[str]]:
    if not values:
        return None
    normalized = [item for item in (value.strip() for value in values) if item]
    return normalized or None
