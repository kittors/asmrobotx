"""存储源配置 CRUD 封装。"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.storage import StorageConfig


class CRUDStorageConfig(CRUDBase[StorageConfig]):
    def get_by_name(self, db: Session, name: str, *, include_deleted: bool = False) -> Optional[StorageConfig]:
        query = self.query(db, include_deleted=include_deleted).filter(self.model.name == name)
        return query.first()

    def get_by_key(self, db: Session, config_key: str, *, include_deleted: bool = False) -> Optional[StorageConfig]:
        query = self.query(db, include_deleted=include_deleted).filter(
            self.model.config_key == config_key
        )
        return query.first()

    def list_all(self, db: Session) -> List[StorageConfig]:
        query = self.query(db)
        # 按创建时间倒序，最近的在前
        query = query.order_by(self.model.create_time.desc())
        return query.all()

    def count(self, db: Session) -> int:
        query = self.query(db).with_entities(func.count(self.model.id))
        return int(query.scalar() or 0)


storage_config_crud = CRUDStorageConfig(StorageConfig)
