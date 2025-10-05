"""用户相关的请求与响应模型定义。"""

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.api.v1.schemas.common import ResponseEnvelope
from app.core.enums import UserStatusEnum


class OrganizationInfo(BaseModel):
    """组织信息的精简表示，用于嵌套在用户资料中。"""

    org_id: int
    org_name: str


class UserInfo(BaseModel):
    """当前登录用户的综合信息视图。"""

    user_id: int
    username: str
    nickname: Optional[str] = None
    status: Optional[str] = None
    organization: Optional[OrganizationInfo]
    roles: list[str]
    permissions: list[str]


UserInfoResponse = ResponseEnvelope[UserInfo]


class UserSummary(BaseModel):
    """用户列表摘要信息。"""

    user_id: int
    username: str
    nickname: Optional[str]
    status: str
    status_label: str
    role_ids: List[int]
    role_names: List[str]
    organization: Optional[OrganizationInfo]
    remark: Optional[str]
    create_time: Optional[str]
    update_time: Optional[str]
    is_active: bool


class UserDetail(UserSummary):
    """用户详情信息。"""


class UserListPayload(BaseModel):
    """用户列表响应的数据部分。"""

    total: int
    items: List[UserSummary]
    page: int
    page_size: int


UserListResponse = ResponseEnvelope[UserListPayload]


class UserCreateRequest(BaseModel):
    """新增用户的请求体。"""

    username: str = Field(..., min_length=1, description="登录用户名")
    password: str = Field(..., min_length=6, description="登录密码")
    nickname: Optional[str] = Field(default=None, description="用户昵称")
    status: str = Field(default=UserStatusEnum.NORMAL.value, description="用户状态")
    role_ids: List[int] = Field(default_factory=list, description="角色 ID 集合")
    remark: Optional[str] = Field(default=None, description="备注")
    organization_id: Optional[int] = Field(default=None, ge=1, description="组织 ID")

    @model_validator(mode="after")
    def _normalize(self) -> "UserCreateRequest":
        self.username = self.username.strip()
        if not self.username:
            raise ValueError("用户名不能为空")

        self.password = self.password.strip()
        if len(self.password) < 6:
            raise ValueError("密码长度不能少于 6 位")

        if self.nickname is not None:
            nickname = self.nickname.strip()
            self.nickname = nickname or None

        self.status = self.status.strip()
        if not self.status:
            raise ValueError("用户状态不能为空")

        if self.remark is not None:
            remark = self.remark.strip()
            self.remark = remark or None

        if self.role_ids:
            unique: List[int] = []
            seen = set()
            for item in self.role_ids:
                if item in seen:
                    continue
                seen.add(item)
                unique.append(item)
            self.role_ids = unique

        return self


class UserUpdateRequest(BaseModel):
    """更新用户的请求体。"""

    nickname: Optional[str] = Field(default=None, description="用户昵称")
    status: Optional[str] = Field(default=None, description="用户状态")
    role_ids: Optional[List[int]] = Field(default=None, description="角色 ID 集合")
    remark: Optional[str] = Field(default=None, description="备注")
    organization_id: Optional[int] = Field(default=None, ge=1, description="组织 ID")

    @model_validator(mode="after")
    def _normalize(self) -> "UserUpdateRequest":
        if self.nickname is not None:
            nickname = self.nickname.strip()
            self.nickname = nickname or None

        if self.status is not None:
            status = self.status.strip()
            if not status:
                raise ValueError("用户状态不能为空")
            self.status = status

        if self.remark is not None:
            remark = self.remark.strip()
            self.remark = remark or None

        if self.role_ids is not None:
            unique: List[int] = []
            seen = set()
            for item in self.role_ids:
                if item in seen:
                    continue
                seen.add(item)
                unique.append(item)
            self.role_ids = unique

        return self


class UserPasswordResetRequest(BaseModel):
    """重置密码的请求体。"""

    password: str = Field(..., min_length=6, description="新密码")

    @model_validator(mode="after")
    def _normalize(self) -> "UserPasswordResetRequest":
        self.password = self.password.strip()
        if len(self.password) < 6:
            raise ValueError("密码长度不能少于 6 位")
        return self


class UserDeletionPayload(BaseModel):
    user_id: int


UserDeletionResponse = ResponseEnvelope[UserDeletionPayload]


class UserPasswordResetPayload(BaseModel):
    user_id: int


UserPasswordResetResponse = ResponseEnvelope[UserPasswordResetPayload]


class ImportFailure(BaseModel):
    row: int
    message: str


class UserImportPayload(BaseModel):
    created: int
    failed: List[ImportFailure]
    total: int


UserImportResponse = ResponseEnvelope[UserImportPayload]


UserMutationResponse = ResponseEnvelope[UserDetail]
