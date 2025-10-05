"""Database bootstrapping utilities."""

from sqlalchemy.orm import Session

from app.core.constants import (
    ADMIN_ROLE,
    DEFAULT_ADMIN_NICKNAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ORGANIZATION_NAME,
    DEFAULT_USER_ROLE,
)
from app.core.enums import RoleStatusEnum, UserStatusEnum
from app.core.security import get_password_hash, verify_password
from app.db import session as db_session
from app.models.base import Base
from app.models.dictionary import DictionaryEntry
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def init_db() -> None:
    """Create tables and seed critical reference data."""
    Base.metadata.create_all(bind=db_session.engine)
    db = db_session.SessionLocal()
    try:
        organization = _ensure_organization(db)
        permissions = _ensure_permissions(db)
        admin_role, user_role = _ensure_roles(db, permissions)
        _ensure_admin_user(db, organization.id, admin_role)
        _ensure_dictionary_entries(db)
        db.commit()
    finally:
        db.close()


def _ensure_organization(db: Session) -> Organization:
    """Ensure a default organization record exists."""
    organization = db.query(Organization).filter(Organization.name == DEFAULT_ORGANIZATION_NAME).first()
    if organization is None:
        organization = Organization(name=DEFAULT_ORGANIZATION_NAME)
        db.add(organization)
        db.flush()
    elif getattr(organization, "is_deleted", False):
        organization.is_deleted = False
    return organization


def _ensure_permissions(db: Session) -> dict[str, Permission]:
    """Guarantee required permission rows are present."""
    seed_permissions = {
        "view_dashboard": {
            "description": "查看仪表盘",
            "type": "route",
        },
        "edit_self_profile": {
            "description": "编辑个人资料",
            "type": "route",
        },
        "manage_users": {
            "description": "管理用户",
            "type": "route",
        },
    }

    permissions: dict[str, Permission] = {}
    for perm_name, meta in seed_permissions.items():
        permission = db.query(Permission).filter(Permission.name == perm_name).first()
        if permission is None:
            permission = Permission(name=perm_name, description=meta["description"], type=meta["type"])
            db.add(permission)
            db.flush()
        elif getattr(permission, "is_deleted", False):
            permission.is_deleted = False
        permissions[perm_name] = permission
    return permissions


def _ensure_roles(db: Session, permissions: dict[str, Permission]) -> tuple[Role, Role]:
    """Create the admin and user roles and map their permissions."""
    admin_role = db.query(Role).filter(Role.name == ADMIN_ROLE).first()
    if admin_role is None:
        admin_role = Role(
            name=ADMIN_ROLE,
            role_key=ADMIN_ROLE,
            status=RoleStatusEnum.NORMAL.value,
            sort_order=1,
        )
        db.add(admin_role)
        db.flush()
    elif getattr(admin_role, "is_deleted", False):
        admin_role.is_deleted = False
    if not getattr(admin_role, "role_key", None):
        admin_role.role_key = ADMIN_ROLE
    if not getattr(admin_role, "status", None):
        admin_role.status = RoleStatusEnum.NORMAL.value
    admin_role.permissions = list(permissions.values())

    user_role = db.query(Role).filter(Role.name == DEFAULT_USER_ROLE).first()
    if user_role is None:
        user_role = Role(
            name=DEFAULT_USER_ROLE,
            role_key=DEFAULT_USER_ROLE,
            status=RoleStatusEnum.NORMAL.value,
            sort_order=2,
        )
        db.add(user_role)
        db.flush()
    elif getattr(user_role, "is_deleted", False):
        user_role.is_deleted = False
    if not getattr(user_role, "role_key", None):
        user_role.role_key = DEFAULT_USER_ROLE
    if not getattr(user_role, "status", None):
        user_role.status = RoleStatusEnum.NORMAL.value
    user_role.permissions = [permissions["view_dashboard"], permissions["edit_self_profile"]]

    return admin_role, user_role


def _ensure_admin_user(db: Session, organization_id: int, admin_role: Role) -> None:
    """Seed an admin user and keep its credentials in sync."""
    admin_user = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
    hashed_password = get_password_hash(DEFAULT_ADMIN_PASSWORD)
    if admin_user is None:
        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            hashed_password=hashed_password,
            nickname=DEFAULT_ADMIN_NICKNAME,
            organization_id=organization_id,
            status=UserStatusEnum.NORMAL.value,
            remark=None,
            is_active=True,
        )
        admin_user.roles = [admin_role]
        db.add(admin_user)
    else:
        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
        if not verify_password(DEFAULT_ADMIN_PASSWORD, admin_user.hashed_password):
            admin_user.hashed_password = hashed_password
        if getattr(admin_user, "is_deleted", False):
            admin_user.is_deleted = False
        if not getattr(admin_user, "nickname", None):
            admin_user.nickname = DEFAULT_ADMIN_NICKNAME
        admin_user.status = UserStatusEnum.NORMAL.value
        admin_user.is_active = True


def _ensure_dictionary_entries(db: Session) -> None:
    """初始化系统所需的字典项，例如图标与状态集合。"""

    seed_dictionary = {
        "display_status": [
            {"value": "show", "label": "显示"},
            {"value": "hidden", "label": "隐藏"},
        ],
        "enable_status": [
            {"value": "enabled", "label": "启用"},
            {"value": "disabled", "label": "停用"},
        ],
    }

    for type_code, entries in seed_dictionary.items():
        for order, entry in enumerate(entries, start=1):
            existing = (
                db.query(DictionaryEntry)
                .filter(
                    DictionaryEntry.type_code == type_code,
                    DictionaryEntry.value == entry["value"],
                )
                .first()
            )

            if existing is None:
                item = DictionaryEntry(
                    type_code=type_code,
                    label=entry["label"],
                    value=entry["value"],
                    description=entry.get("description"),
                    sort_order=order,
                )
                db.add(item)
                db.flush()
            else:
                if getattr(existing, "is_deleted", False):
                    existing.is_deleted = False
                existing.label = entry["label"]
                existing.description = entry.get("description")
                existing.sort_order = order
