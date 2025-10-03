"""枚举定义：约束角色以及权限类型的可选值。"""

from enum import Enum


class RoleEnum(str, Enum):
    ADMIN = "admin"
    USER = "user"


class PermissionTypeEnum(str, Enum):
    ROUTE = "route"
    MENU = "menu"
    DATA_SCOPE = "data_scope"


class AccessControlTypeEnum(str, Enum):
    """访问控制项在前端渲染时的类型分类。"""

    MENU = "menu"
    BUTTON = "button"


class OperationLogTypeEnum(str, Enum):
    """操作日志的业务类型枚举。"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    GRANT = "grant"
    EXPORT = "export"
    IMPORT = "import"
    FORCE_OFFLINE = "force_logout"
    CLEAN = "clean"
    OTHER = "other"


class OperationLogStatusEnum(str, Enum):
    """操作日志状态标识。"""

    SUCCESS = "success"
    FAILURE = "failure"


class LoginLogStatusEnum(str, Enum):
    """登录日志状态标识。"""

    SUCCESS = "success"
    FAILURE = "failure"
