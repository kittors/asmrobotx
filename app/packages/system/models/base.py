"""模型基类：统一声明式基类以及多对多关联表。"""

from datetime import datetime

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


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, primary_key=True, index=True),
    Column("role_id", Integer, primary_key=True, index=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, primary_key=True, index=True),
    Column("permission_id", Integer, primary_key=True, index=True),
)

role_access_controls = Table(
    "role_access_controls",
    Base.metadata,
    Column("role_id", Integer, primary_key=True, index=True),
    Column("access_control_id", Integer, primary_key=True, index=True),
)
