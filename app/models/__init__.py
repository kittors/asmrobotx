"""模型包初始化，便于统一导入 ORM 实体。"""

from app.models.log import LoginLog, OperationLog

__all__ = [
    "OperationLog",
    "LoginLog",
]
