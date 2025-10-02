"""系统字典模型：统一维护常用的可配置选项。"""

from typing import Optional

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class DictionaryEntry(TimestampMixin, SoftDeleteMixin, Base):
    """字典条目，按照 ``type_code`` 分类存储选项值。"""

    __tablename__ = "dictionary_entries"
    __table_args__ = (
        UniqueConstraint("type_code", "value", name="uq_dictionary_entries_type_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    type_code: Mapped[str] = mapped_column(String(100), index=True)
    label: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
