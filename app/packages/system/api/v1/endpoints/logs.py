"""日志管理相关的路由定义。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.logs import (
    LoginLogDeletionResponse,
    LoginLogListResponse,
    MonitorRuleCreate,
    MonitorRuleDeletionResponse,
    MonitorRuleDetailResponse,
    MonitorRuleListResponse,
    MonitorRuleUpdate,
    OperationLogDeletionResponse,
    OperationLogDetailResponse,
    OperationLogListResponse,
)
from app.packages.system.core.constants import HTTP_STATUS_BAD_REQUEST
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.logger import logger
from app.packages.system.models.user import User
from app.packages.system.services.log_service import log_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/operations", response_model=OperationLogListResponse)
def list_operation_logs(
    request: Request,
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
    current_user: User = Depends(get_current_active_user),
) -> OperationLogListResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = log_service.list_operation_logs(
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
            module_name="日志管理",
            business_type="query",
            class_method="app.packages.system.api.v1.endpoints.logs.list_operation_logs",
            request_body={
                "module": module,
                "operator_name": operator_name,
                "operator_ip": operator_ip,
                "operation_types": operation_types,
                "statuses": statuses,
                "request_uri": request_uri,
                "start_time": start_time,
                "end_time": end_time,
                "page": page,
                "page_size": page_size,
            },
            response_body=_summarize_list_response(response_payload),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/operations/export")
def export_operation_logs(
    request: Request,
    module: Optional[str] = Query(None),
    operator_name: Optional[str] = Query(None),
    operator_ip: Optional[str] = Query(None),
    operation_types: Optional[list[str]] = Query(None),
    statuses: Optional[list[str]] = Query(None),
    request_uri: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_headers: Optional[dict[str, Any]] = None

    try:
        response = log_service.export_operation_logs(
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
            module_name="日志管理",
            business_type="export",
            class_method="app.packages.system.api.v1.endpoints.logs.export_operation_logs",
            request_body={
                "module": module,
                "operator_name": operator_name,
                "operator_ip": operator_ip,
                "operation_types": operation_types,
                "statuses": statuses,
                "request_uri": request_uri,
                "start_time": start_time,
                "end_time": end_time,
            },
            response_body=response_headers,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/operations/{log_number}", response_model=OperationLogDetailResponse)
def get_operation_log_detail(
    request: Request,
    log_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OperationLogDetailResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = log_service.get_operation_log_detail(db, log_number=log_number)
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
            module_name="日志管理",
            business_type="query",
            class_method="app.packages.system.api.v1.endpoints.logs.get_operation_log_detail",
            request_body={"log_number": log_number},
            response_body={"log_number": log_number} if response_payload else None,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


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


@router.get("/monitor-rules", response_model=MonitorRuleListResponse)
def list_monitor_rules(
    request_uri: Optional[str] = Query(None, description="请求地址模糊匹配"),
    http_method: Optional[str] = Query(None, description="HTTP 方法"),
    match_mode: Optional[str] = Query(None, description="匹配模式: exact/prefix"),
    is_enabled: Optional[bool] = Query(None, description="是否启用"),
    operation_type_code: Optional[str] = Query(None, description="规则类型编码"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MonitorRuleListResponse:
    return log_service.list_monitor_rules(
        db,
        request_uri=request_uri,
        http_method=http_method,
        match_mode=match_mode,
        is_enabled=is_enabled,
        operation_type_code=operation_type_code,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/monitor-rules",
    response_model=MonitorRuleDetailResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_monitor_rule(
    payload: MonitorRuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MonitorRuleDetailResponse:
    return log_service.create_monitor_rule(db, payload=payload.model_dump(exclude_none=True))


@router.get("/monitor-rules/{rule_id}", response_model=MonitorRuleDetailResponse)
def get_monitor_rule_detail(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MonitorRuleDetailResponse:
    return log_service.get_monitor_rule(db, rule_id=rule_id)


@router.put("/monitor-rules/{rule_id}", response_model=MonitorRuleDetailResponse)
def update_monitor_rule(
    rule_id: int,
    payload: MonitorRuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MonitorRuleDetailResponse:
    return log_service.update_monitor_rule(
        db,
        rule_id=rule_id,
        payload=payload.model_dump(exclude_unset=True, exclude_none=False),
    )


@router.delete("/monitor-rules/{rule_id}", response_model=MonitorRuleDeletionResponse)
def delete_monitor_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MonitorRuleDeletionResponse:
    return log_service.delete_monitor_rule(db, rule_id=rule_id)


@router.get("/logins", response_model=LoginLogListResponse)
def list_login_logs(
    request: Request,
    username: Optional[str] = Query(None, description="用户名模糊匹配"),
    ip_address: Optional[str] = Query(None, description="登录 IP 模糊匹配"),
    statuses: Optional[list[str]] = Query(None, description="登录状态过滤，可多选"),
    start_time: Optional[str] = Query(None, description="开始时间，格式: YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式: YYYY-MM-DD HH:MM:SS"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LoginLogListResponse:
    started_at = datetime.now(timezone.utc)
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = log_service.list_login_logs(
            db,
            username=username,
            ip_address=ip_address,
            statuses=_normalize_sequence(statuses),
            start_time=_parse_datetime(start_time),
            end_time=_parse_datetime(end_time),
            page=page,
            page_size=page_size,
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
            module_name="日志管理",
            business_type="query",
            class_method="app.packages.system.api.v1.endpoints.logs.list_login_logs",
            request_body={
                "username": username,
                "ip_address": ip_address,
                "statuses": statuses,
                "start_time": start_time,
                "end_time": end_time,
                "page": page,
                "page_size": page_size,
            },
            response_body=_summarize_list_response(response_payload),
            status=status,
            error_message=error_message,
            started_at=started_at,
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


def _record_operation_log(
    *,
    db: Session,
    request: Request,
    current_user: User,
    module_name: str,
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
                "module": module_name,
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
        logger.warning("Failed to record log module operation log: %s", exc)


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
        logger.debug("Failed to serialize log module payload: %s", exc)
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path


def _summarize_list_response(payload: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not payload:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        summary = {key: data.get(key) for key in ("total", "page", "page_size")}
        return summary
    return None
