"""日志模型定义：包含操作日志与登录日志的结构。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class OperationLog(TimestampMixin, SoftDeleteMixin, Base):
    """操作日志记录，覆盖接口调用的关键审计信息。"""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    log_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(100))
    business_type: Mapped[str] = mapped_column(String(32))
    operator_name: Mapped[str] = mapped_column(String(50))
    operator_department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    operator_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    operator_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    request_uri: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    class_method: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_ms: Mapped[int] = mapped_column(Integer, default=0)
    operate_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LoginLog(TimestampMixin, SoftDeleteMixin, Base):
    """登录日志记录，体现系统访问行为。"""

    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    visit_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50))
    client_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    login_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    operating_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success")
    message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    login_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
