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

    DIRECTORY = "directory"
    MENU = "menu"
    BUTTON = "button"
