"""角色 CRUD：管理角色实体的常用操作。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.role import Role


class CRUDRole(CRUDBase[Role]):
    """提供角色实体的便捷查询方法。"""

    def get_by_name(self, db: Session, name: str) -> Optional[Role]:
        """根据唯一名称查询角色。"""
        query = self.query(db).filter(Role.name == name)
        return query.first()

    def get_by_key(self, db: Session, role_key: str) -> Optional[Role]:
        """按照权限字符查询角色。"""
        query = self.query(db).filter(Role.role_key == role_key)
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
        query = self.query(db)

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

    def list_by_ids(self, db: Session, ids: Iterable[int]) -> List[Role]:
        """根据主键集合批量查询角色。"""

        id_set = {item for item in ids if item is not None}
        if not id_set:
            return []

        query = self.query(db).filter(self.model.id.in_(id_set))
        return query.all()


role_crud = CRUDRole(Role)
