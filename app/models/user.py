"""用户模型：描述系统中的账号及其所属资源。"""

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UserStatusEnum
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, user_roles


class User(TimestampMixin, SoftDeleteMixin, Base):
    """用户实体，与角色存在多对多关系，可选地挂载在某个组织下。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    organization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id"))
    status: Mapped[str] = mapped_column(String(20), default=UserStatusEnum.NORMAL.value, index=True)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="users")
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
    )
