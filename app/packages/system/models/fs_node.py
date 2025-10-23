"""统一的文件系统节点模型（文件与目录合并）。

存储规则：
- path：以 '/' 开头，不以 '/' 结尾；根目录不入库；
- is_dir：目录为 True，文件为 False；
- name：当前节点名（basename），目录与文件均不含路径分隔符；
- 对于文件：size_bytes/mime_type 有意义；目录则 size_bytes=0、mime_type=NULL。
"""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    OrganizationOwnedMixin,
)


class FsNode(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fs_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    storage_id: Mapped[int] = mapped_column(Integer, index=True)
    # 以 '/' 开头，不以 '/' 结尾；示例："/docs"、"/docs/a.txt"、"/a.jpg"
    path: Mapped[str] = mapped_column(String(1024), index=True)
    # 基名：不含 '/'
    name: Mapped[str] = mapped_column(String(255), index=True)
    is_dir: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("storage_id", "path", name="uq_fs_nodes_storage_path"),
    )

