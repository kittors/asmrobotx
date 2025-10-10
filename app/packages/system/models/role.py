"""角色模型：定义用户可被赋予的角色及其关联关系。"""

from typing import List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.packages.system.core.enums import RoleStatusEnum
from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    OrganizationOwnedMixin,
    role_access_controls,
    role_permissions,
    user_roles,
    role_organizations,
)


class Role(CreatedByMixin, OrganizationOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    """角色实体，汇集权限并通过多对多关系关联用户。"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    role_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=RoleStatusEnum.NORMAL.value, index=True)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_roles,
        primaryjoin="Role.id == user_roles.c.role_id",
        secondaryjoin="User.id == user_roles.c.user_id",
        back_populates="roles",
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        primaryjoin="Role.id == role_permissions.c.role_id",
        secondaryjoin="Permission.id == role_permissions.c.permission_id",
        back_populates="roles",
    )
    access_controls: Mapped[List["AccessControlItem"]] = relationship(
        "AccessControlItem",
        secondary=role_access_controls,
        primaryjoin="Role.id == role_access_controls.c.role_id",
        secondaryjoin="AccessControlItem.id == role_access_controls.c.access_control_id",
        back_populates="roles",
    )
    organizations: Mapped[List["Organization"]] = relationship(
        "Organization",
        secondary=role_organizations,
        primaryjoin="Role.id == role_organizations.c.role_id",
        secondaryjoin="Organization.id == role_organizations.c.organization_id",
        back_populates="roles",
    )
