"""访问控制项的数据库访问封装。"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.access_control import AccessControlItem


class CRUDAccessControl(CRUDBase[AccessControlItem]):
    """提供访问控制项的便捷查询方法。"""

    def list_all(self, db: Session) -> List[AccessControlItem]:
        """返回所有未删除的访问控制项，按照排序值与主键排序。"""
        query = db.query(self.model)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return query.order_by(self.model.sort_order, self.model.id).all()

    def get_by_permission_code(
        self,
        db: Session,
        permission_code: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> Optional[AccessControlItem]:
        """按照唯一的权限字符检索访问控制项。"""
        query = db.query(self.model).filter(self.model.permission_code == permission_code)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        if exclude_id is not None:
            query = query.filter(self.model.id != exclude_id)
        return query.first()

    def has_children(self, db: Session, item_id: int) -> bool:
        """判断指定访问控制项是否存在未删除的子级。"""
        query = db.query(self.model.id).filter(self.model.parent_id == item_id)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return query.first() is not None


access_control_crud = CRUDAccessControl(AccessControlItem)
