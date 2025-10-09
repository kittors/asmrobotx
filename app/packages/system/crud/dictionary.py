"""系统字典的数据库访问方法。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.dictionary import DictionaryEntry


class CRUDDictionary(CRUDBase[DictionaryEntry]):
    """提供按类型查询与维护字典项的能力。"""

    def get_items_by_type(self, db: Session, type_code: str) -> List[DictionaryEntry]:
        """按照类型编码返回排序后的字典项列表。"""
        items, _ = self.list_with_filters(db, type_code=type_code, keyword=None, skip=0, limit=1000)
        return items

    def list_with_filters(
        self,
        db: Session,
        *,
        type_code: str,
        keyword: Optional[str],
        skip: int,
        limit: int,
    ) -> Tuple[List[DictionaryEntry], int]:
        """根据类型与搜索关键字返回分页后的字典项列表。"""
        query = db.query(self.model).filter(self.model.type_code == type_code)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))

        if keyword:
            trimmed = keyword.strip()
            if trimmed:
                pattern = f"%{trimmed}%"
                query = query.filter(
                    or_(
                        self.model.label.ilike(pattern),
                        self.model.value.ilike(pattern),
                    )
                )

        total = query.count()
        items = (
            query.order_by(self.model.sort_order.asc(), self.model.id.asc())
            .offset(max(skip, 0))
            .limit(max(limit, 1))
            .all()
        )
        return items, total

    def get_by_value(
        self,
        db: Session,
        *,
        type_code: str,
        value: str,
        exclude_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> Optional[DictionaryEntry]:
        """按照类型与值查询字典项，可排除指定 ID。"""
        query = db.query(self.model).filter(
            self.model.type_code == type_code,
            self.model.value == value,
        )
        if exclude_id is not None:
            query = query.filter(self.model.id != exclude_id)
        if hasattr(self.model, "is_deleted") and not include_deleted:
            query = query.filter(self.model.is_deleted.is_(False))
        return query.first()

    def soft_delete_by_type(self, db: Session, *, type_code: str) -> int:
        """将指定类型下的字典项批量软删除，返回受影响数量。"""
        query = db.query(self.model).filter(self.model.type_code == type_code)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        items = query.all()
        for item in items:
            item.is_deleted = True
            db.add(item)
        return len(items)


dictionary_crud = CRUDDictionary(DictionaryEntry)
