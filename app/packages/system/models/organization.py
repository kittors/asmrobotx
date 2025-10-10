"""组织模型：描述用户所属的组织机构。"""

from typing import List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    role_organizations,
)


class Organization(CreatedByMixin, TimestampMixin, SoftDeleteMixin, Base):
    """组织实体，支持层级结构：通过 `parent_id` 形成树，便于表达“公司-部门”。"""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    parent: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        primaryjoin=lambda: foreign(Organization.parent_id) == Organization.id,
        remote_side=lambda: Organization.id,
        foreign_keys=lambda: Organization.parent_id,
        back_populates="children",
    )
    children: Mapped[List["Organization"]] = relationship(
        "Organization",
        primaryjoin=lambda: foreign(Organization.parent_id) == Organization.id,
        foreign_keys=lambda: Organization.parent_id,
        back_populates="parent",
    )

    users: Mapped[List["User"]] = relationship(
        "User",
        primaryjoin="User.organization_id == Organization.id",
        foreign_keys="User.organization_id",
        back_populates="organization",
    )
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_organizations,
        primaryjoin="Organization.id == role_organizations.c.organization_id",
        secondaryjoin="Role.id == role_organizations.c.role_id",
        back_populates="organizations",
    )
