"""本地目录变更记录模型。"""

from typing import Optional
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.packages.system.models.base import Base, SoftDeleteMixin, TimestampMixin


class DirectoryChangeRecord(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "directory_change_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    storage_id: Mapped[int] = mapped_column()
    action: Mapped[str] = mapped_column(String(32))
    path_old: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    path_new: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    operate_time: Mapped["datetime"] = mapped_column(DateTime(timezone=True))
    # extra jsonb 不在 ORM 层强约束，后续按需扩展
