"""角色 CRUD：管理角色实体的常用操作。"""

from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.role import Role


class CRUDRole(CRUDBase[Role]):
    """提供角色实体的便捷查询方法。"""

    def get_by_name(self, db: Session, name: str) -> Optional[Role]:
        """根据唯一名称查询角色。"""
        query = db.query(Role).filter(Role.name == name)
        if hasattr(Role, "is_deleted"):
            query = query.filter(Role.is_deleted.is_(False))
        return query.first()


role_crud = CRUDRole(Role)
