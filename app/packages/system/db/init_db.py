"""Database bootstrapping utilities."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Tuple

from sqlalchemy.orm import Session

from app.packages.system.core.constants import (
    ADMIN_ROLE,
    DEFAULT_ADMIN_NICKNAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ORGANIZATION_NAME,
)
from app.packages.system.core.enums import RoleEnum, RoleStatusEnum, UserStatusEnum
from app.packages.system.core.security import get_password_hash
from app.packages.system.db import session as db_session
from app.packages.system.models.base import Base
from app.packages.system.models.dictionary import DictionaryEntry, DictionaryType
from app.packages.system.models.organization import Organization
from app.packages.system.models.role import Role
from app.packages.system.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_DICTIONARY_TYPES: Dict[str, Tuple[str, str]] = {
    "display_status": ("显示状态", "用于表示菜单或组件在前端的显示控制"),
    "enabled_status": ("启用状态", "用于标记资源当前是否可用"),
    "icon_list": ("图标列表", "为前端图标选择器提供可用图标"),
    "operation_log_type": ("操作日志类型", "区分操作日志的业务动作"),
}

DEFAULT_DICTIONARY_ITEMS: Dict[str, Iterable[Tuple[str, str, str]]] = {
    "display_status": (
        ("显示", "show", "用于表示菜单或组件应在前端展示"),
        ("隐藏", "hidden", "用于表示菜单或组件应在前端隐藏"),
    ),
    "enabled_status": (
        ("启用", "enabled", "标记条目当前处于启用状态"),
        ("停用", "disabled", "标记条目当前处于停用状态"),
    ),
    "icon_list": (
        ("工具箱", "tool-case", "工具图标"),
        ("设置", "settings", "设置图标"),
        ("搜索", "search", "通用搜索图标"),
        ("外链", "link", "外链/跳转图标"),
        ("地图定位", "map-pinned", "地理定位图标"),
        ("菜单", "menu", "菜单/列表图标"),
    ),
    "operation_log_type": (
        ("新增", "create", "新增数据"),
        ("修改", "update", "修改数据"),
        ("删除", "delete", "删除数据"),
        ("查询", "query", "查询数据"),
        ("授权", "grant", "权限授权"),
        ("导出", "export", "数据导出"),
        ("导入", "import", "数据导入"),
        ("强退", "force_logout", "强制下线"),
        ("清除数据", "clean", "批量清除数据"),
        ("其他", "other", "其它操作"),
    ),
}


def init_db() -> None:
    """Create all database tables if they do not exist and seed baseline data."""
    Base.metadata.create_all(bind=db_session.engine)

    session = db_session.SessionLocal()
    try:
        _seed_core_entities(session)
        session.commit()
    except Exception:  # pragma: no cover - initialization failures should not crash gracefully
        session.rollback()
        logger.exception("Failed to seed default data during database initialization")
        raise
    finally:
        session.close()


def _seed_core_entities(db: Session) -> None:
    """Ensure the baseline organization, role, administrator and dictionaries exist."""
    organization = (
        db.query(Organization)
        .filter(
            Organization.name == DEFAULT_ORGANIZATION_NAME,
            Organization.is_deleted.is_(False),
        )
        .first()
    )
    if organization is None:
        organization = Organization(name=DEFAULT_ORGANIZATION_NAME)
        db.add(organization)
        db.flush()

    admin_role = (
        db.query(Role)
        .filter(Role.name == ADMIN_ROLE, Role.is_deleted.is_(False))
        .first()
    )
    if admin_role is None:
        admin_role = Role(
            name=ADMIN_ROLE,
            role_key=RoleEnum.ADMIN.value,
            status=RoleStatusEnum.NORMAL.value,
            sort_order=1,
        )
        db.add(admin_role)
        db.flush()
    else:
        admin_role.role_key = admin_role.role_key or RoleEnum.ADMIN.value
        admin_role.status = admin_role.status or RoleStatusEnum.NORMAL.value
        db.add(admin_role)

    admin_user = (
        db.query(User)
        .filter(User.username == DEFAULT_ADMIN_USERNAME, User.is_deleted.is_(False))
        .first()
    )
    if admin_user is None:
        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            nickname=DEFAULT_ADMIN_NICKNAME,
            status=UserStatusEnum.NORMAL.value,
            is_active=True,
            organization_id=organization.id if organization else None,
        )
        db.add(admin_user)
        db.flush()
        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
    else:
        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
        if not admin_user.nickname:
            admin_user.nickname = DEFAULT_ADMIN_NICKNAME
        if not admin_user.organization_id and organization is not None:
            admin_user.organization_id = organization.id
        if admin_user.status is None:
            admin_user.status = UserStatusEnum.NORMAL.value
        admin_user.is_active = True
        db.add(admin_user)

    for order, (type_code, (display_name, description)) in enumerate(DEFAULT_DICTIONARY_TYPES.items(), start=1):
        dictionary_type = (
            db.query(DictionaryType)
            .filter(
                DictionaryType.type_code == type_code,
                DictionaryType.is_deleted.is_(False),
            )
            .first()
        )
        if dictionary_type is None:
            dictionary_type = DictionaryType(
                type_code=type_code,
                display_name=display_name,
                description=description,
                sort_order=order,
            )
            db.add(dictionary_type)
            db.flush()
        else:
            updated = False
            if not dictionary_type.display_name:
                dictionary_type.display_name = display_name
                updated = True
            if dictionary_type.description is None and description is not None:
                dictionary_type.description = description
                updated = True
            if dictionary_type.sort_order is None:
                dictionary_type.sort_order = order
                updated = True
            elif dictionary_type.sort_order != order:
                dictionary_type.sort_order = dictionary_type.sort_order or order
            if updated:
                db.add(dictionary_type)

    for type_code, entries in DEFAULT_DICTIONARY_ITEMS.items():
        dictionary_type = (
            db.query(DictionaryType)
            .filter(
                DictionaryType.type_code == type_code,
                DictionaryType.is_deleted.is_(False),
            )
            .first()
        )
        if dictionary_type is None:
            display_name, description = DEFAULT_DICTIONARY_TYPES.get(type_code, (type_code, None))
            dictionary_type = DictionaryType(
                type_code=type_code,
                display_name=display_name,
                description=description,
                sort_order=len(DEFAULT_DICTIONARY_TYPES) + 1,
            )
            db.add(dictionary_type)
            db.flush()

        for index, (label, value, description) in enumerate(entries, start=1):
            exists = (
                db.query(DictionaryEntry)
                .filter(
                    DictionaryEntry.type_code == type_code,
                    DictionaryEntry.value == value,
                    DictionaryEntry.is_deleted.is_(False),
                )
                .first()
            )
            if exists:
                continue
            db.add(
                DictionaryEntry(
                    type_code=type_code,
                    label=label,
                    value=value,
                    description=description,
                    sort_order=index,
                )
            )
