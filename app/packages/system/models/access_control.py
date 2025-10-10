"""访问控制项模型：用于描述菜单与按钮等权限节点。"""

from typing import Any, List, Optional

from sqlalchemy import Boolean, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.packages.system.core.enums import AccessControlTypeEnum
from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    OrganizationOwnedMixin,
    role_access_controls,
)


class AccessControlItem(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    """用于构建权限树的访问控制实体。"""

    __tablename__ = "access_control_items"
    __table_args__ = (
        UniqueConstraint("permission_code", name="uq_access_control_items_permission_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    type: Mapped[str] = mapped_column(String(20), default=AccessControlTypeEnum.MENU.value)
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_code: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    route_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enabled_status: Mapped[str] = mapped_column(String(50), default="enabled")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    component_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    route_params: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    keep_alive: Mapped[bool] = mapped_column(Boolean, default=False)

    parent: Mapped[Optional["AccessControlItem"]] = relationship(
        "AccessControlItem",
        primaryjoin=lambda: foreign(AccessControlItem.parent_id) == AccessControlItem.id,
        remote_side=lambda: AccessControlItem.id,
        foreign_keys=lambda: AccessControlItem.parent_id,
        back_populates="children",
    )
    children: Mapped[List["AccessControlItem"]] = relationship(
        "AccessControlItem",
        primaryjoin=lambda: foreign(AccessControlItem.parent_id) == AccessControlItem.id,
        foreign_keys=lambda: AccessControlItem.parent_id,
        back_populates="parent",
    )
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_access_controls,
        primaryjoin="AccessControlItem.id == role_access_controls.c.access_control_id",
        secondaryjoin="Role.id == role_access_controls.c.role_id",
        back_populates="access_controls",
    )
