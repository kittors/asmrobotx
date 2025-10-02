"""用户服务：提供用户相关的响应组装逻辑。"""

from app.core.constants import HTTP_STATUS_OK
from app.core.responses import create_response
from app.models.user import User


class UserService:
    """聚合用户信息，生成前端友好的数据结构。"""

    def build_user_profile(self, user: User) -> dict:
        """整理用户的组织、角色及权限列表，构造统一响应。"""
        organization = None
        if user.organization is not None:
            organization = {
                "org_id": user.organization.id,
                "org_name": user.organization.name,
            }

        roles = [role.name for role in user.roles]
        permissions = sorted({perm.name for role in user.roles for perm in role.permissions})

        data = {
            "user_id": user.id,
            "username": user.username,
            "organization": organization,
            "roles": roles,
            "permissions": permissions,
        }
        return create_response("获取用户信息成功", data, HTTP_STATUS_OK)


user_service = UserService()
