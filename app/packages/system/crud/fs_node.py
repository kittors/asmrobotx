"""FsNode CRUD。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.fs_node import FsNode


class CRUDFsNode(CRUDBase[FsNode]):
    def get_by_path(self, db: Session, *, storage_id: int, path: str) -> FsNode | None:
        return (
            self.query(db)
            .filter(FsNode.storage_id == storage_id)
            .filter(FsNode.path == path)
            .first()
        )


fs_node_crud = CRUDFsNode(FsNode)

