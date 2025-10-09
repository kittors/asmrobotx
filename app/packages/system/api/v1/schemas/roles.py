"""角色管理相关的请求与响应模型。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.packages.system.api.v1.schemas.common import ResponseEnvelope
from app.packages.system.core.enums import RoleStatusEnum


class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, description="角色名称")
    role_key: str = Field(..., min_length=1, description="权限字符")
    sort_order: int = Field(default=0, ge=0, description="显示顺序")
    status: str = Field(default=RoleStatusEnum.NORMAL.value, description="角色状态")
    permission_ids: List[int] = Field(default_factory=list, description="访问权限 ID 集合")
    remark: Optional[str] = Field(default=None, description="备注信息")

    @model_validator(mode="after")
    def _trim_fields(self) -> "RoleBase":
        self.name = self.name.strip()
        self.role_key = self.role_key.strip()
        if not self.name:
            raise ValueError("角色名称不能为空")
        if not self.role_key:
            raise ValueError("权限字符不能为空")
        if self.remark is not None:
            trimmed = self.remark.strip()
            self.remark = trimmed or None
        if self.permission_ids:
            unique_order = []
            seen = set()
            for item in self.permission_ids:
                if item in seen:
                    continue
                seen.add(item)
                unique_order.append(item)
            self.permission_ids = unique_order
        return self


class RoleCreateRequest(RoleBase):
    """新建角色的请求体。"""


class RoleUpdateRequest(RoleBase):
    """更新角色的请求体。"""


class RoleStatusUpdateRequest(BaseModel):
    """变更角色状态的请求体。"""

    status: str = Field(..., description="角色状态")

    @model_validator(mode="after")
    def _trim_status(self) -> "RoleStatusUpdateRequest":
        self.status = self.status.strip()
        if not self.status:
            raise ValueError("角色状态不能为空")
        return self


class RoleSummary(BaseModel):
    """角色列表项摘要。"""

    role_id: int
    role_name: str
    role_key: str
    sort_order: int
    status: str
    status_label: str
    remark: Optional[str]
    create_time: Optional[str]


class RoleDetail(RoleSummary):
    """角色详细信息。"""

    update_time: Optional[str]
    permission_ids: List[int]
    permission_codes: List[str]


class RoleListPayload(BaseModel):
    """角色列表响应的数据部分。"""

    total: int
    items: List[RoleSummary]
    page: int
    page_size: int


RoleListResponse = ResponseEnvelope[RoleListPayload]
RoleDetailResponse = ResponseEnvelope[RoleDetail]
RoleMutationResponse = ResponseEnvelope[RoleDetail]


class RoleDeletionPayload(BaseModel):
    role_id: int


RoleDeletionResponse = ResponseEnvelope[RoleDeletionPayload]
