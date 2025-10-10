"""用户 CRUD：集中管理用户相关的数据操作。"""

from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session, selectinload

from app.packages.system.core.enums import UserStatusEnum
from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.role import Role
from app.packages.system.models.user import User
from app.packages.system.core.datascope import get_scope


class CRUDUser(CRUDBase[User]):
    """封装常用的用户查询方法，供业务层复用。"""

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """根据唯一用户名获取用户实例。"""
        query = self.query(db).filter(User.username == username)
        return query.first()

    def list_with_filters(
        self,
        db: Session,
        *,
        username: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[list[User], int]:
        """按照多条件过滤用户并返回分页结果。"""

        query = self.query(db)

        if username:
            query = query.filter(self.model.username.ilike(f"%{username.strip()}%"))
        if statuses:
            normalized = {status.strip().lower() for status in statuses if status}
            if normalized:
                query = query.filter(self.model.status.in_(normalized))
        if start_time and end_time:
            query = query.filter(self.model.create_time.between(start_time, end_time))
        elif start_time:
            query = query.filter(self.model.create_time >= start_time)
        elif end_time:
            query = query.filter(self.model.create_time <= end_time)

        total = query.count()
        items = (
            query.options(
                selectinload(self.model.roles),
                selectinload(self.model.organization),
            )
            .order_by(self.model.id.asc())
            .offset(max(skip, 0))
            .limit(max(limit, 1))
            .all()
        )
        return items, total

    def list_by_usernames(self, db: Session, usernames: Iterable[str]) -> list[User]:
        """批量根据用户名获取用户，用于导入去重等场景。"""
        tokens = {item.strip() for item in usernames if item and item.strip()}
        if not tokens:
            return []
        query = self.query(db).filter(self.model.username.in_(tokens))
        return query.all()

    def create_with_roles(
        self,
        db: Session,
        *,
        username: str,
        hashed_password: str,
        organization_id: Optional[int],
        roles: List[Role],
        nickname: Optional[str] = None,
        status: Optional[str] = None,
        remark: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> User:
        """创建用户并附加角色集合，保持事务提交的一致性。"""
        resolved_status = status or UserStatusEnum.NORMAL.value

        effective_active = is_active if is_active is not None else resolved_status == UserStatusEnum.NORMAL.value

        # 默认组织：优先使用显式传入；否则回落到当前数据域
        scope = get_scope()
        effective_org_id = organization_id if organization_id is not None else scope.organization_id

        user = User(
            username=username,
            hashed_password=hashed_password,
            nickname=nickname,
            organization_id=effective_org_id,
            status=resolved_status,
            remark=remark,
            is_active=effective_active,
        )
        # 记录创建人（若处于认证上下文）
        if hasattr(user, "created_by") and scope.user_id is not None:
            user.created_by = scope.user_id
        user.roles = roles
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


user_crud = CRUDUser(User)
