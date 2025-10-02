"""权限 CRUD：管理权限实体的常用数据库操作。"""

from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.permission import Permission


class CRUDPermission(CRUDBase[Permission]):
    """封装权限实体的查询逻辑，避免在业务层重复编写。"""

    def get_by_name(self, db: Session, name: str) -> Optional[Permission]:
        """根据唯一名称检索权限记录。"""
        query = db.query(Permission).filter(Permission.name == name)
        if hasattr(Permission, "is_deleted"):
            query = query.filter(Permission.is_deleted.is_(False))
        return query.first()


permission_crud = CRUDPermission(Permission)
