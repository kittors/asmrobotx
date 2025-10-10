"""权限 CRUD：管理权限实体的常用数据库操作。"""

from typing import Optional

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.permission import Permission


class CRUDPermission(CRUDBase[Permission]):
    """封装权限实体的查询逻辑，避免在业务层重复编写。"""

    def get_by_name(self, db: Session, name: str) -> Optional[Permission]:
        """根据唯一名称检索权限记录。"""
        query = self.query(db).filter(Permission.name == name)
        return query.first()


permission_crud = CRUDPermission(Permission)
