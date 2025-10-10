"""组织相关的响应模型定义。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.packages.system.api.v1.schemas.common import ResponseEnvelope


class OrganizationItem(BaseModel):
    """组织列表中的单项记录，适用于下拉选择。"""

    org_id: int
    org_name: str


OrganizationListResponse = ResponseEnvelope[list[OrganizationItem]]


class OrganizationTreeNode(BaseModel):
    """组织树节点。"""

    org_id: int
    org_name: str
    parent_id: Optional[int]
    sort_order: int
    children: list["OrganizationTreeNode"]


OrganizationTreeResponse = ResponseEnvelope[list[OrganizationTreeNode]]
