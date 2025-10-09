"""组织模型：描述用户所属的组织机构。"""

from typing import List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Organization(TimestampMixin, SoftDeleteMixin, Base):
    """组织实体，记录组织名称并维护与用户的一对多关系。"""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    users: Mapped[List["User"]] = relationship(
        "User",
        primaryjoin="User.organization_id == Organization.id",
        foreign_keys="User.organization_id",
        back_populates="organization",
    )
