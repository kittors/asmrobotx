"""组织相关的响应模型定义。"""

from pydantic import BaseModel

from app.api.v1.schemas.common import ResponseEnvelope


class OrganizationItem(BaseModel):
    """组织列表中的单项记录，适用于下拉选择。"""

    org_id: int
    org_name: str


OrganizationListResponse = ResponseEnvelope[list[OrganizationItem]]
