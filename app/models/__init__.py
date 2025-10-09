"""模型包初始化，便于统一导入 ORM 实体并触发模型注册。"""

from app.models.access_control import AccessControlItem
from app.models.dictionary import DictionaryEntry
from app.models.log import LoginLog, OperationLog, OperationLogMonitorRule
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User

__all__ = [
    "AccessControlItem",
    "DictionaryEntry",
    "OperationLog",
    "LoginLog",
    "OperationLogMonitorRule",
    "Organization",
    "Permission",
    "Role",
    "User",
]
