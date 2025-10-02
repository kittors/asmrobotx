"""访问控制相关的请求与响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.api.v1.schemas.common import ResponseEnvelope
from app.core.enums import AccessControlTypeEnum


class AccessControlCreateRequest(BaseModel):
    """新建访问控制项时的请求体。"""

    parent_id: Optional[int] = Field(default=None, ge=0)
    name: str = Field(..., min_length=1)
    type: AccessControlTypeEnum
    icon: Optional[str] = None
    is_external: Optional[bool] = False
    permission_code: str = Field(..., min_length=1)
    route_path: Optional[str] = None
    display_status: Optional[str] = None
    enabled_status: str = Field(..., min_length=1)
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_by_type(self) -> "AccessControlCreateRequest":
        if self.type in {AccessControlTypeEnum.DIRECTORY, AccessControlTypeEnum.MENU}:
            if not self.route_path or not self.route_path.strip():
                raise ValueError("目录或菜单必须提供路由地址")
            if not self.display_status or not self.display_status.strip():
                raise ValueError("目录或菜单必须提供显示状态")
        if not self.enabled_status or not self.enabled_status.strip():
            raise ValueError("停用状态必填")
        return self


class AccessControlUpdateRequest(BaseModel):
    """更新访问控制项时的请求体。"""

    name: str = Field(..., min_length=1)
    icon: Optional[str] = None
    is_external: Optional[bool] = False
    permission_code: str = Field(..., min_length=1)
    route_path: Optional[str] = None
    display_status: Optional[str] = None
    enabled_status: str = Field(..., min_length=1)
    sort_order: Optional[int] = Field(default=None, ge=0)


class AccessControlReorderRequest(BaseModel):
    """拖拽排序时的请求体。"""

    target_parent_id: Optional[int] = Field(default=None, ge=0)
    target_index: int = Field(..., ge=0)


class AccessControlDetail(BaseModel):
    """访问控制项的完整信息。"""

    id: int
    parent_id: Optional[int]
    name: str
    type: AccessControlTypeEnum
    icon: Optional[str]
    is_external: bool
    permission_code: str
    route_path: Optional[str]
    display_status: Optional[str]
    enabled_status: str
    sort_order: int
    create_time: datetime
    update_time: datetime


class AccessControlTreeNode(BaseModel):
    """用于树形结构展示的访问控制节点。"""

    id: int
    parent_id: Optional[int]
    name: str
    type: AccessControlTypeEnum
    icon: Optional[str]
    is_external: bool
    permission_code: str
    route_path: Optional[str]
    display_status: Optional[str]
    enabled_status: str
    effective_display_status: Optional[str]
    effective_enabled_status: str
    sort_order: int
    children: list["AccessControlTreeNode"] = Field(default_factory=list)


AccessControlTreeResponse = ResponseEnvelope[list[AccessControlTreeNode]]
AccessControlDetailResponse = ResponseEnvelope[AccessControlDetail]
AccessControlMutationResponse = ResponseEnvelope[AccessControlDetail]
AccessControlDeletionResponse = ResponseEnvelope[Optional[None]]
AccessControlReorderResponse = ResponseEnvelope[AccessControlDetail]


AccessControlTreeNode.model_rebuild()
