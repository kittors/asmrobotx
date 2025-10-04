"""角色模型：定义用户可被赋予的角色及其关联关系。"""

from typing import List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import RoleStatusEnum
from app.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    role_access_controls,
    role_permissions,
    user_roles,
)


class Role(TimestampMixin, SoftDeleteMixin, Base):
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
        back_populates="roles",
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
    )
    access_controls: Mapped[List["AccessControlItem"]] = relationship(
        "AccessControlItem",
        secondary=role_access_controls,
        back_populates="roles",
    )
