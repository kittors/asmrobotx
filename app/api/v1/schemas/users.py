"""用户相关的响应模型定义。"""

from typing import Optional

from pydantic import BaseModel

from app.api.v1.schemas.common import ResponseEnvelope


class OrganizationInfo(BaseModel):
    """组织信息的精简表示，用于嵌套在用户资料中。"""

    org_id: int
    org_name: str


class UserInfo(BaseModel):
    """当前登录用户的综合信息视图。"""

    user_id: int
    username: str
    organization: Optional[OrganizationInfo]
    roles: list[str]
    permissions: list[str]


UserInfoResponse = ResponseEnvelope[UserInfo]
