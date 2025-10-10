"""字典类型的数据库访问方法。"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.dictionary import DictionaryType


class CRUDDictionaryType(CRUDBase[DictionaryType]):
    """提供字典类型的常见查询与操作。"""

    def get_by_code(
        self,
        db: Session,
        type_code: str,
        *,
        include_deleted: bool = False,
    ) -> Optional[DictionaryType]:
        """根据类型编码查询字典类型。"""
        if include_deleted:
            query = self.query(db, include_deleted=True)
        else:
            query = self.query(db)
        return query.filter(self.model.type_code == type_code).first()

    def list_with_keyword(self, db: Session, *, keyword: Optional[str] = None) -> List[DictionaryType]:
        """按照关键字（匹配编码或显示名称）返回全部字典类型。"""
        query = self.query(db)

        if keyword:
            trimmed = keyword.strip()
            if trimmed:
                pattern = f"%{trimmed}%"
                query = query.filter(
                    or_(
                        self.model.type_code.ilike(pattern),
                        self.model.display_name.ilike(pattern),
                    )
                )

        return query.order_by(self.model.sort_order.asc(), self.model.id.asc()).all()


dictionary_type_crud = CRUDDictionaryType(DictionaryType)

__all__ = ["dictionary_type_crud"]
