"""权限模型：存储系统中可授权的单项能力。"""

from typing import List, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PermissionTypeEnum
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, role_permissions


class Permission(TimestampMixin, SoftDeleteMixin, Base):
    """权限实体，可被多个角色复用，并区分不同类型。"""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(50), default=PermissionTypeEnum.ROUTE.value)

    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        primaryjoin="Permission.id == role_permissions.c.permission_id",
        secondaryjoin="Role.id == role_permissions.c.role_id",
        back_populates="permissions",
    )
