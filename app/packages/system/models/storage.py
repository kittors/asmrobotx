"""存储源配置模型：支持 S3 与本地文件系统两类后端。"""

from typing import Optional

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.packages.system.models.base import Base, SoftDeleteMixin, TimestampMixin


class StorageConfig(TimestampMixin, SoftDeleteMixin, Base):
    """存储源配置，保存访问不同存储后端所需的连接信息。

    说明：
    - ``type`` 仅允许取值 "S3" 与 "LOCAL"；
    - S3 类型字段：``region``、``bucket_name``、``path_prefix``、``access_key_id``、``secret_access_key``；
    - 本地类型字段：``local_root_path``；
    - 为防止误删，仅实现软删除。
    """

    __tablename__ = "storage_configs"
    __table_args__ = (
        UniqueConstraint("name", name="uq_storage_configs_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    type: Mapped[str] = mapped_column(String(16))  # "S3" or "LOCAL"

    # S3 only
    region: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bucket_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    path_prefix: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_key_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    secret_access_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # LOCAL only
    local_root_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

