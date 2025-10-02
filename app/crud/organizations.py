"""组织 CRUD：管理组织相关的数据库操作。"""

from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.organization import Organization


class CRUDOrganization(CRUDBase[Organization]):
    """提供组织实体的便捷查询方法。"""

    def get_by_name(self, db: Session, name: str) -> Optional[Organization]:
        """按照唯一名称检索组织信息。"""
        query = db.query(Organization).filter(Organization.name == name)
        if hasattr(Organization, "is_deleted"):
            query = query.filter(Organization.is_deleted.is_(False))
        return query.first()


organization_crud = CRUDOrganization(Organization)
