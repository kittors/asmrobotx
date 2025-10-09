"""组织列表路由定义。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.organizations import OrganizationItem, OrganizationListResponse
from app.packages.system.core.constants import HTTP_STATUS_OK
from app.packages.system.core.dependencies import get_db
from app.packages.system.core.responses import create_response
from app.packages.system.crud.organizations import organization_crud

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=OrganizationListResponse)
def list_organizations(db: Session = Depends(get_db)) -> OrganizationListResponse:
    """返回所有组织信息，便于前端在注册等场景展示下拉列表。"""
    organizations = organization_crud.get_multi(db)
    data = [OrganizationItem(org_id=org.id, org_name=org.name) for org in organizations]
    return create_response("获取组织机构列表成功", data, HTTP_STATUS_OK)
