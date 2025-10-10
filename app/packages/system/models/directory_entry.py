"""目录实体模型：用于在“严格读库”的文件列表中展示空目录/已有目录。

存储规则：
- path：以 '/' 开头，不以 '/' 结尾；根目录不入库（即 '/' 不存储）。
"""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    OrganizationOwnedMixin,
)


class DirectoryEntry(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "directory_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    storage_id: Mapped[int] = mapped_column(Integer, index=True)
    path: Mapped[str] = mapped_column(String(1024), index=True)  # 以 '/' 开头，不以 '/' 结尾

    __table_args__ = (
        UniqueConstraint("storage_id", "path", name="uq_directory_entries_storage_path"),
    )

