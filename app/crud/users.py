"""用户 CRUD：集中管理用户相关的数据操作。"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.role import Role
from app.models.user import User


class CRUDUser(CRUDBase[User]):
    """封装常用的用户查询方法，供业务层复用。"""

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """根据唯一用户名获取用户实例。"""
        query = db.query(User).filter(User.username == username)
        if hasattr(User, "is_deleted"):
            query = query.filter(User.is_deleted.is_(False))
        return query.first()

    def create_with_roles(
        self,
        db: Session,
        *,
        username: str,
        hashed_password: str,
        organization_id: int,
        roles: List[Role],
    ) -> User:
        """创建用户并附加角色集合，保持事务提交的一致性。"""
        user = User(
            username=username,
            hashed_password=hashed_password,
            organization_id=organization_id,
        )
        user.roles = roles
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


user_crud = CRUDUser(User)
