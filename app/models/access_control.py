"""访问控制项模型：用于描述目录、菜单与按钮等权限节点。"""

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AccessControlTypeEnum
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class AccessControlItem(TimestampMixin, SoftDeleteMixin, Base):
    """用于构建权限树的访问控制实体。"""

    __tablename__ = "access_control_items"
    __table_args__ = (
        UniqueConstraint("permission_code", name="uq_access_control_items_permission_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("access_control_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), index=True)
    type: Mapped[str] = mapped_column(String(20), default=AccessControlTypeEnum.DIRECTORY.value)
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_code: Mapped[str] = mapped_column(String(100), index=True)
    route_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enabled_status: Mapped[str] = mapped_column(String(50), default="enabled")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped[Optional["AccessControlItem"]] = relationship(
        "AccessControlItem",
        remote_side="AccessControlItem.id",
        back_populates="children",
    )
    children: Mapped[List["AccessControlItem"]] = relationship(
        "AccessControlItem",
        back_populates="parent",
    )
