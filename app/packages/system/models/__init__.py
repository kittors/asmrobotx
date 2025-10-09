"""模型包初始化，便于统一导入 ORM 实体并触发模型注册。"""

from app.packages.system.models.access_control import AccessControlItem
from app.packages.system.models.dictionary import DictionaryEntry, DictionaryType
from app.packages.system.models.log import LoginLog, OperationLog, OperationLogMonitorRule
from app.packages.system.models.organization import Organization
from app.packages.system.models.permission import Permission
from app.packages.system.models.role import Role
from app.packages.system.models.user import User
from app.packages.system.models.storage import StorageConfig

__all__ = [
    "AccessControlItem",
    "DictionaryEntry",
    "DictionaryType",
    "OperationLog",
    "LoginLog",
    "OperationLogMonitorRule",
    "Organization",
    "Permission",
    "Role",
    "User",
    "StorageConfig",
]
