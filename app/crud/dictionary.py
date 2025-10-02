"""系统字典的数据库访问方法。"""

from typing import List

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.dictionary import DictionaryEntry


class CRUDDictionary(CRUDBase[DictionaryEntry]):
    """提供按类型查询字典项的能力。"""

    def get_items_by_type(self, db: Session, type_code: str) -> List[DictionaryEntry]:
        """按照类型编码返回排序后的字典项列表。"""
        query = db.query(self.model).filter(self.model.type_code == type_code)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return query.order_by(self.model.sort_order, self.model.id).all()


dictionary_crud = CRUDDictionary(DictionaryEntry)
