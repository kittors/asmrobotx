"""组织 CRUD：管理组织相关的数据库操作。"""

from typing import Optional, Iterable

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.organization import Organization


class CRUDOrganization(CRUDBase[Organization]):
    """提供组织实体的便捷查询方法。"""

    def get_by_name(self, db: Session, name: str) -> Optional[Organization]:
        """按照唯一名称检索组织信息。"""
        query = db.query(Organization).filter(Organization.name == name)
        if hasattr(Organization, "is_deleted"):
            query = query.filter(Organization.is_deleted.is_(False))
        return query.first()

    def list_by_ids(self, db: Session, ids: Iterable[int]) -> list[Organization]:
        """根据 ID 集合批量获取组织。"""
        tokens = {int(i) for i in ids if i is not None}
        if not tokens:
            return []
        query = db.query(Organization).filter(Organization.id.in_(tokens))
        if hasattr(Organization, "is_deleted"):
            query = query.filter(Organization.is_deleted.is_(False))
        return query.all()

    def list_all(self, db: Session) -> list[Organization]:
        """获取全部组织，统一排序。"""
        query = self.query(db)
        # 若表具备 sort_order 列，则按 sort_order,id 排序
        if hasattr(Organization, "sort_order"):
            query = query.order_by(Organization.sort_order.asc(), Organization.id.asc())
        return query.all()


organization_crud = CRUDOrganization(Organization)
