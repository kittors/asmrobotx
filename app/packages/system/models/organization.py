"""组织模型：描述用户所属的组织机构。"""

from typing import List, Optional

from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from app.packages.system.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    CreatedByMixin,
    role_organizations,
)


class Organization(CreatedByMixin, TimestampMixin, SoftDeleteMixin, Base):
    """组织实体，支持层级结构：通过 `parent_id` 形成树，便于表达“公司-部门”。

    - 仅在同一父节点下限制名称唯一（允许不同分支出现同名“研发部”）。
    - `sort_order` 用于同级展示顺序。
    - 防止自引用（`parent_id != id`）。
    """

    __tablename__ = "organizations"
    __table_args__ = (
        # 仅同一父节点下唯一
        UniqueConstraint("parent_id", "name", name="uq_organizations_parent_name"),
        # 防止自引用
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_organizations_no_self_parent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    # 邻接表模型：自引用外键；硬删除时置空，业务内采用软删除
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # 同级排序
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)

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
