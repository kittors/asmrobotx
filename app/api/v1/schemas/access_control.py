"""访问控制相关的请求与响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    permission_code: Optional[str] = None
    route_path: Optional[str] = None
    display_status: Optional[str] = None
    enabled_status: str = Field(..., min_length=1)
    sort_order: int = Field(default=0, ge=0)
    component_path: Optional[str] = None
    route_params: Optional[dict[str, Any]] = None
    keep_alive: Optional[bool] = False

    @model_validator(mode="after")
    def validate_by_type(self) -> "AccessControlCreateRequest":
        if self.type == AccessControlTypeEnum.MENU:
            if not self.display_status or not self.display_status.strip():
                raise ValueError("菜单必须提供显示状态")
            if self.route_path is not None and not self.route_path.strip():
                raise ValueError("菜单路由地址不能为空字符串")
            if self.component_path is not None and not self.component_path.strip():
                raise ValueError("菜单组件路径不能为空字符串")
        if self.permission_code is not None:
            trimmed_code = self.permission_code.strip()
            if not trimmed_code:
                self.permission_code = None
            else:
                self.permission_code = trimmed_code
        if self.type == AccessControlTypeEnum.BUTTON and not (self.permission_code and self.permission_code.strip()):
            raise ValueError("按钮必须提供权限字符")
        if not self.enabled_status or not self.enabled_status.strip():
            raise ValueError("停用状态必填")
        return self


class AccessControlUpdateRequest(BaseModel):
    """更新访问控制项时的请求体。"""

    name: str = Field(..., min_length=1)
    icon: Optional[str] = None
    is_external: Optional[bool] = False
    permission_code: Optional[str] = None
    route_path: Optional[str] = None
    display_status: Optional[str] = None
    enabled_status: str = Field(..., min_length=1)
    sort_order: Optional[int] = Field(default=None, ge=0)
    component_path: Optional[str] = None
    route_params: Optional[dict[str, Any]] = None
    keep_alive: Optional[bool] = False

    @model_validator(mode="after")
    def validate_permission_code(self) -> "AccessControlUpdateRequest":
        if self.permission_code is not None:
            trimmed_code = self.permission_code.strip()
            if not trimmed_code:
                self.permission_code = None
            else:
                self.permission_code = trimmed_code
        return self


class AccessControlDetail(BaseModel):
    """访问控制项的完整信息。"""

    id: int
    parent_id: Optional[int]
    name: str
    type: AccessControlTypeEnum
    icon: Optional[str]
    is_external: bool
    permission_code: Optional[str]
    route_path: Optional[str]
    display_status: Optional[str]
    enabled_status: str
    sort_order: int
    component_path: Optional[str]
    route_params: Optional[dict[str, Any]]
    keep_alive: bool
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
    permission_code: Optional[str]
    route_path: Optional[str]
    display_status: Optional[str]
    enabled_status: str
    effective_display_status: Optional[str]
    effective_enabled_status: str
    sort_order: int
    component_path: Optional[str]
    route_params: Optional[dict[str, Any]]
    keep_alive: bool
    children: list["AccessControlTreeNode"] = Field(default_factory=list)


AccessControlTreeResponse = ResponseEnvelope[list[AccessControlTreeNode]]
AccessControlDetailResponse = ResponseEnvelope[AccessControlDetail]
AccessControlMutationResponse = ResponseEnvelope[AccessControlDetail]
AccessControlDeletionResponse = ResponseEnvelope[Optional[None]]
AccessControlTreeNode.model_rebuild()
