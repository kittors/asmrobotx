"""目录实体 CRUD。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.directory_entry import DirectoryEntry


class CRUDDirectoryEntry(CRUDBase[DirectoryEntry]):
    def get_by_path(self, db: Session, *, storage_id: int, path: str) -> DirectoryEntry | None:
        return (
            self.query(db)
            .filter(DirectoryEntry.storage_id == storage_id)
            .filter(DirectoryEntry.path == path)
            .first()
        )


directory_entry_crud = CRUDDirectoryEntry(DirectoryEntry)

