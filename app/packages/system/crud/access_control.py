"""访问控制项的数据库访问封装。"""

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.access_control import AccessControlItem
from app.packages.system.models.base import role_access_controls


class CRUDAccessControl(CRUDBase[AccessControlItem]):
    """提供访问控制项的便捷查询方法。"""

    def list_all(self, db: Session) -> List[AccessControlItem]:
        """返回所有未删除的访问控制项，按照排序值与主键排序。"""
        query = self.query(db)
        return query.order_by(self.model.sort_order, self.model.id).all()

    def get_by_permission_code(
        self,
        db: Session,
        permission_code: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> Optional[AccessControlItem]:
        """按照唯一的权限字符检索访问控制项。"""
        query = self.query(db).filter(self.model.permission_code == permission_code)
        if exclude_id is not None:
            query = query.filter(self.model.id != exclude_id)
        return query.first()

    def has_children(self, db: Session, item_id: int) -> bool:
        """判断指定访问控制项是否存在未删除的子级。"""
        query = self.query(db).with_entities(self.model.id).filter(self.model.parent_id == item_id)
        return query.first() is not None

    def list_by_ids(self, db: Session, ids: Iterable[int]) -> List[AccessControlItem]:
        """根据一组主键批量检索访问控制项。"""
        id_set = {item for item in ids if item is not None}
        if not id_set:
            return []
        query = self.query(db).filter(self.model.id.in_(id_set))
        return query.all()

    def list_permitted_by_roles(self, db: Session, role_ids: Iterable[int]) -> List[AccessControlItem]:
        """按角色集合返回其被授权的访问控制项（未删除）。"""
        ids = {int(x) for x in role_ids if x is not None}
        if not ids:
            return []
        # 直接 join 关联表，避免从 Role 实体再取
        query = (
            self.query(db)
            .join(
                role_access_controls,
                self.model.id == role_access_controls.c.access_control_id,
            )
            .filter(role_access_controls.c.role_id.in_(ids))
            .distinct()
        )
        return query.all()


access_control_crud = CRUDAccessControl(AccessControlItem)
