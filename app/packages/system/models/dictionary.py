"""系统字典模型：统一维护常用的可配置选项。"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    OrganizationOwnedMixin,
)


class DictionaryType(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    """字典类型定义，描述一组字典项的用途与元数据。"""

    __tablename__ = "dictionary_types"
    __table_args__ = (
        UniqueConstraint("type_code", name="uq_dictionary_types_type_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    type_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class DictionaryEntry(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    """字典条目，按照 ``type_code`` 分类存储选项值。"""

    __tablename__ = "dictionary_entries"
    __table_args__ = (
        UniqueConstraint("type_code", "value", name="uq_dictionary_entries_type_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    type_code: Mapped[str] = mapped_column(String(100), ForeignKey("dictionary_types.type_code"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
