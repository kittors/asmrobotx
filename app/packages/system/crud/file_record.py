"""文件记录 CRUD。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.file_record import FileRecord


class CRUDFileRecord(CRUDBase[FileRecord]):
    pass


file_record_crud = CRUDFileRecord(FileRecord)

