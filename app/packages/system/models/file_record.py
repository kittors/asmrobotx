"""文件上传记录模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    OrganizationOwnedMixin,
)


class FileRecord(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "file_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    storage_id: Mapped[int] = mapped_column(Integer, index=True)
    directory: Mapped[str] = mapped_column(String(1024))
    original_name: Mapped[str] = mapped_column(String(255))
    alias_name: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(64), default="general")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
