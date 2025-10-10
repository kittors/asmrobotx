"""模型基类：统一声明式基类、通用审计/归属字段与多对多关联表。

本模块集中提供：
- Base：SQLAlchemy 声明式基类，带统一命名约定；
- TimestampMixin：`create_time`、`update_time`；
- SoftDeleteMixin：`is_deleted`；
- CreatedByMixin：`created_by`（创建人用户 ID，可空）；
- OrganizationOwnedMixin：`organization_id`（归属组织 ID，可空）；
- 三个多对多关联表（user_roles/role_permissions/role_access_controls），
  补充了时间戳与软删除等审计字段，便于后续排查或扩展。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, Table, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import expression

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """全局声明式基类，附带一致的命名约定，便于迁移与调试。"""

    metadata = metadata_obj


class TimestampMixin:
    """通用时间戳字段，为记录新增、更新提供审计能力。"""

    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """软删除字段，避免物理删除导致数据丢失。"""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        server_default=expression.false(),
        nullable=False,
    )


# 记录创建人（用户 ID）。注意：允许为 NULL，以兼容系统脚本或历史数据。
class CreatedByMixin:
    # 记录创建人（强制必填，默认 1=admin）
    created_by: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, server_default=expression.text("1")
    )


# 记录归属组织（组织 ID）。注意：允许为 NULL，以支持全局记录或历史数据。
class OrganizationOwnedMixin:
    # 记录归属组织（强制必填，默认 1=研发部）
    organization_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, server_default=expression.text("1")
    )


# 多对多关系表：增加审计字段，便于追踪是谁在何时创建了关联；
# 当前业务未启用“软删除关联”的语义，但保留 `is_deleted` 字段以备将来扩展。
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, primary_key=True, index=True),
    Column("role_id", Integer, primary_key=True, index=True),
    Column("create_time", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "update_time",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    Column("is_deleted", Boolean, server_default=expression.false(), nullable=False),
    Column("created_by", Integer, nullable=True, index=True),
    # 避免与主键 organization_id 冲突，审计字段命名为 owner_org_id
    Column("owner_org_id", Integer, nullable=True, index=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, primary_key=True, index=True),
    Column("permission_id", Integer, primary_key=True, index=True),
    Column("create_time", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "update_time",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    Column("is_deleted", Boolean, server_default=expression.false(), nullable=False),
    Column("created_by", Integer, nullable=True, index=True),
    Column("owner_org_id", Integer, nullable=True, index=True),
)

role_access_controls = Table(
    "role_access_controls",
    Base.metadata,
    Column("role_id", Integer, primary_key=True, index=True),
    Column("access_control_id", Integer, primary_key=True, index=True),
    Column("create_time", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "update_time",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    Column("is_deleted", Boolean, server_default=expression.false(), nullable=False),
    Column("created_by", Integer, nullable=True, index=True),
    Column("organization_id", Integer, nullable=True, index=True),
)

# 角色-组织多对多：用于“数据权限分配”，一个角色可授权访问多个组织的数据
role_organizations = Table(
    "role_organizations",
    Base.metadata,
    Column("role_id", Integer, primary_key=True, index=True),
    Column("organization_id", Integer, primary_key=True, index=True),
    Column("create_time", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "update_time",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    Column("is_deleted", Boolean, server_default=expression.false(), nullable=False),
    Column("created_by", Integer, nullable=True, index=True),
    Column("owner_org_id", Integer, nullable=True, index=True),
)
