"""访问控制管理相关的路由定义。"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.schemas.access_control import (
    AccessControlCreateRequest,
    AccessControlDeletionResponse,
    AccessControlDetailResponse,
    AccessControlMutationResponse,
    AccessControlTreeResponse,
    AccessControlUpdateRequest,
)
from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.services.access_control_service import access_control_service

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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> AccessControlMutationResponse:
    """创建新的访问控制节点。"""
    return access_control_service.create(db, payload=payload.model_dump(exclude_none=True))


@router.put("/{item_id}", response_model=AccessControlMutationResponse)
def update_access_control_item(
    item_id: int,
    payload: AccessControlUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> AccessControlMutationResponse:
    """更新现有访问控制节点。"""
    return access_control_service.update(db, item_id=item_id, payload=payload.model_dump(exclude_unset=True))


@router.delete("/{item_id}", response_model=AccessControlDeletionResponse)
def delete_access_control_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> AccessControlDeletionResponse:
    """删除指定的访问控制节点。"""
    return access_control_service.delete(db, item_id=item_id)
