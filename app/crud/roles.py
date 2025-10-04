"""角色 CRUD：管理角色实体的常用操作。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Tuple

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

    def get_by_key(self, db: Session, role_key: str) -> Optional[Role]:
        """按照权限字符查询角色。"""
        query = db.query(Role).filter(Role.role_key == role_key)
        if hasattr(Role, "is_deleted"):
            query = query.filter(Role.is_deleted.is_(False))
        return query.first()

    def list_with_filters(
        self,
        db: Session,
        *,
        name: Optional[str] = None,
        role_key: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[list[Role], int]:
        """综合查询角色列表并返回总数。"""
        query = db.query(self.model)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))

        if name:
            query = query.filter(self.model.name.ilike(f"%{name.strip()}%"))
        if role_key:
            query = query.filter(self.model.role_key.ilike(f"%{role_key.strip()}%"))
        if statuses:
            normalized = {status.strip().lower() for status in statuses if status}
            if normalized:
                query = query.filter(self.model.status.in_(normalized))
        if start_time and end_time:
            query = query.filter(self.model.create_time.between(start_time, end_time))
        elif start_time:
            query = query.filter(self.model.create_time >= start_time)
        elif end_time:
            query = query.filter(self.model.create_time <= end_time)

        total = query.count()
        items = (
            query.order_by(self.model.sort_order.asc(), self.model.id.asc())
            .offset(max(skip, 0))
            .limit(max(limit, 1))
            .all()
        )
        return items, total


role_crud = CRUDRole(Role)
