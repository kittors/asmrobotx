"""目录变更记录 CRUD。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.directory_change_record import DirectoryChangeRecord


class CRUDDirectoryChangeRecord(CRUDBase[DirectoryChangeRecord]):
    pass


directory_change_record_crud = CRUDDirectoryChangeRecord(DirectoryChangeRecord)

