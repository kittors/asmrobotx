"""系统字典相关的路由定义。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.dictionary import (
    DictionaryItemCreateRequest,
    DictionaryItemDeletionResponse,
    DictionaryItemListResponse,
    DictionaryItemMutationResponse,
    DictionaryItemUpdateRequest,
    DictionaryTypeCreateRequest,
    DictionaryTypeDeletionResponse,
    DictionaryTypeListResponse,
    DictionaryTypeMutationResponse,
    DictionaryTypeUpdateRequest,
)
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.logger import logger
from app.packages.system.core.timezone import now as tz_now
from app.packages.system.models.user import User
from app.packages.system.services.dictionary_service import dictionary_service
from app.packages.system.services.log_service import log_service

router = APIRouter(prefix="/dictionaries", tags=["dictionaries"])
type_router = APIRouter(prefix="/dictionary_types", tags=["dictionary_types"])


@type_router.get("", response_model=DictionaryTypeListResponse)
def list_dictionary_types(
    keyword: Optional[str] = Query(None, description="按类型编码或显示名称模糊搜索"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DictionaryTypeListResponse:
    """返回全部字典类型列表。"""
    return dictionary_service.list_types(db, keyword=keyword)


@type_router.post("", response_model=DictionaryTypeMutationResponse)
def create_dictionary_type(
    payload: DictionaryTypeCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DictionaryTypeMutationResponse:
    """创建新的字典类型。"""
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump()

    try:
        response_payload = dictionary_service.create_type(
            db,
            type_code=body["type_code"],
            display_name=body["display_name"],
            description=body.get("description"),
            sort_order=body.get("sort_order"),
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
            class_method="app.packages.system.api.v1.endpoints.dictionaries.create_dictionary_type",
            request_body=body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@type_router.put("/{type_code}", response_model=DictionaryTypeMutationResponse)
def update_dictionary_type(
    type_code: str,
    payload: DictionaryTypeUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DictionaryTypeMutationResponse:
    """更新字典类型信息。"""
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump(exclude_none=True)
    audit_body = {"type_code": type_code, **body}

    try:
        response_payload = dictionary_service.update_type(
            db,
            type_code=type_code,
            display_name=payload.display_name,
            description=payload.description,
            sort_order=payload.sort_order,
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
            class_method="app.packages.system.api.v1.endpoints.dictionaries.update_dictionary_type",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@type_router.delete("/{type_code}", response_model=DictionaryTypeDeletionResponse)
def delete_dictionary_type(
    type_code: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DictionaryTypeDeletionResponse:
    """删除指定字典类型及其字典项。"""
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = dictionary_service.delete_type(db, type_code=type_code)
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
            class_method="app.packages.system.api.v1.endpoints.dictionaries.delete_dictionary_type",
            request_body={"type_code": type_code},
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/{type_code}", response_model=DictionaryItemListResponse)
def list_dictionary_items(
    type_code: str,
    keyword: Optional[str] = Query(None, description="按显示文本或实际值模糊搜索"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=200, description="每页展示数量"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DictionaryItemListResponse:
    """根据类型编码返回字典项列表。"""
    return dictionary_service.list_by_type(
        db,
        type_code=type_code,
        keyword=keyword,
        page=page,
        size=size,
    )


@router.post("", response_model=DictionaryItemMutationResponse)
def create_dictionary_item(
    payload: DictionaryItemCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DictionaryItemMutationResponse:
    """创建新的字典项。"""
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump()

    try:
        response_payload = dictionary_service.create_item(
            db,
            type_code=body["type_code"],
            label=body["label"],
            value=body["value"],
            description=body.get("description"),
            sort_order=body.get("sort_order"),
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
            class_method="app.packages.system.api.v1.endpoints.dictionaries.create_dictionary_item",
            request_body=body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.put("/{item_id}", response_model=DictionaryItemMutationResponse)
def update_dictionary_item(
    item_id: int,
    payload: DictionaryItemUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DictionaryItemMutationResponse:
    """更新字典项。"""
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None
    body = payload.model_dump(exclude_none=True)
    audit_body = {"id": item_id, **body}

    try:
        response_payload = dictionary_service.update_item(
            db,
            item_id=item_id,
            label=payload.label,
            value=payload.value,
            description=payload.description,
            sort_order=payload.sort_order,
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
            class_method="app.packages.system.api.v1.endpoints.dictionaries.update_dictionary_item",
            request_body=audit_body,
            response_body=response_payload,
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.delete("/{item_id}", response_model=DictionaryItemDeletionResponse)
def delete_dictionary_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DictionaryItemDeletionResponse:
    """删除指定字典项。"""
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    response_payload: Optional[dict[str, Any]] = None

    try:
        response_payload = dictionary_service.delete_item(db, item_id=item_id)
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
            class_method="app.packages.system.api.v1.endpoints.dictionaries.delete_dictionary_item",
            request_body={"id": item_id},
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
    """记录系统字典管理相关的操作日志。"""

    finished_at = tz_now()
    cost_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
    status_value = status if status in {"success", "failure"} else "other"

    try:
        request_payload = request_body if request_body is not None else _build_request_payload_with_query(request)

        log_service.record_operation_log(
            db,
            payload={
                "module": "系统字典数据管理",
                "business_type": business_type,
                "operator_name": current_user.username,
                "operator_department": None,
                "operator_ip": _extract_client_ip(request),
                "operator_location": None,
                "request_method": request.method,
                "request_uri": _build_request_uri(request),
                "class_method": class_method,
                "request_params": _safe_json_dump(request_payload),
                "response_params": _safe_json_dump(response_body),
                "status": status_value,
                "error_message": error_message,
                "cost_ms": cost_ms,
                "operate_time": finished_at,
            },
        )
    except Exception as exc:  # pragma: no cover - 日志失败不可阻断主流程
        logger.warning("Failed to record dictionary operation log: %s", exc)


def _extract_client_ip(request: Request) -> Optional[str]:
    for header in ("x-forwarded-for", "x-real-ip", "x-client-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _safe_json_dump(payload: Optional[Any]) -> Optional[str]:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover - 防御性策略
        logger.debug("Failed to serialize dictionary log payload: %s", exc)
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path


def _build_request_payload_with_query(request: Request) -> Optional[dict[str, Any]]:
    query_items = list(request.query_params.multi_items())
    if not query_items:
        return None
    return {"query": query_items}
