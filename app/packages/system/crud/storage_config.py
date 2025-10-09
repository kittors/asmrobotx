"""存储源配置 CRUD 封装。"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.storage import StorageConfig


class CRUDStorageConfig(CRUDBase[StorageConfig]):
    def get_by_name(self, db: Session, name: str, *, include_deleted: bool = False) -> Optional[StorageConfig]:
        query = db.query(self.model).filter(self.model.name == name)
        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return query.first()

    def list_all(self, db: Session) -> List[StorageConfig]:
        query = db.query(self.model)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        # 按创建时间倒序，最近的在前
        query = query.order_by(self.model.create_time.desc())
        return query.all()

    def count(self, db: Session) -> int:
        query = db.query(func.count(self.model.id))
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return int(query.scalar() or 0)


storage_config_crud = CRUDStorageConfig(StorageConfig)

