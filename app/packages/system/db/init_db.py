"""Database bootstrapping utilities."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
import os
import re

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
from app.packages.system.models.dictionary import DictionaryType
from app.packages.system.models.organization import Organization
from app.packages.system.models.role import Role
from app.packages.system.models.user import User
from app.packages.system.crud.storage_config import storage_config_crud
from app.packages.system.models.storage import StorageConfig
from app.packages.system.models.file_record import FileRecord  # noqa: F401 - ensure table creation in tests
from app.packages.system.models.fs_node import FsNode  # noqa: F401 - ensure table creation in tests
from app.packages.system.models.access_control import AccessControlItem

logger = logging.getLogger(__name__)

"""
移除了 Python 侧的字典类型/字典项默认数据，改为依赖 SQL 种子脚本：
scripts/db/init/v1/data/001_seed_data.sql。

为兼容测试环境（使用 SQLite，且不会自动执行上述 SQL），在初始化时会尝试
从该 SQL 文件中提取与字典相关的 INSERT 语句并执行一次（若数据库中已存在
典型的字典类型则跳过），确保幂等。
"""


def init_db() -> None:
    """Create all database tables if they do not exist and seed baseline data."""
    Base.metadata.create_all(bind=db_session.engine)

    session = db_session.SessionLocal()
    try:
        _seed_core_entities(session)
        _seed_default_monitor_rules(session)
        _seed_default_storage_if_needed(session)
        _seed_access_controls_from_sql_if_needed(session)
        _seed_dictionaries_from_sql_if_needed(session)
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
        organization = Organization(name=DEFAULT_ORGANIZATION_NAME, created_by=1)
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
            created_by=1,
            organization_id=organization.id if organization else None,
        )
        db.add(admin_role)
        db.flush()
    else:
        admin_role.role_key = admin_role.role_key or RoleEnum.ADMIN.value
        admin_role.status = admin_role.status or RoleStatusEnum.NORMAL.value
        db.add(admin_role)

    # 确保默认用户角色存在
    user_role = (
        db.query(Role)
        .filter(Role.name == RoleEnum.USER.value, Role.is_deleted.is_(False))
        .first()
    )
    if user_role is None:
        user_role = Role(
            name=RoleEnum.USER.value,
            role_key=RoleEnum.USER.value,
            status=RoleStatusEnum.NORMAL.value,
            sort_order=2,
            created_by=1,
            organization_id=organization.id if organization else None,
        )
        db.add(user_role)
        db.flush()

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
            created_by=1,
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
        if not getattr(admin_user, "created_by", None):
            admin_user.created_by = 1
        db.add(admin_user)

    # 字典相关的默认数据从 SQL 脚本注入，不在此处维护。


def _seed_default_monitor_rules(db: Session) -> None:
    """确保关键的监听规则存在（例如对日志接口本身的禁用规则）。"""
    from app.packages.system.models.log import OperationLogMonitorRule

    existing = (
        db.query(OperationLogMonitorRule)
        .filter(
            OperationLogMonitorRule.request_uri == "/api/v1/logs/operations",
            OperationLogMonitorRule.http_method == "ALL",
            OperationLogMonitorRule.match_mode == "prefix",
            OperationLogMonitorRule.is_deleted.is_(False),
        )
        .first()
    )
    if existing is None:
        from app.packages.system.models.organization import Organization
        from app.packages.system.core.constants import DEFAULT_ORGANIZATION_NAME

        org_id = (
            db.query(Organization.id)
            .filter(Organization.name == DEFAULT_ORGANIZATION_NAME)
            .scalar()
        )
        rule = OperationLogMonitorRule(
            name="接口调用日志列表",
            request_uri="/api/v1/logs/operations",
            http_method="ALL",
            match_mode="prefix",
            is_enabled=False,
            description="获取接口调用的日志列表",
            operation_type_code="query",
            created_by=1,
            organization_id=org_id or 1,
        )
        db.add(rule)
        db.flush()


def _seed_access_controls_from_sql_if_needed(db: Session) -> None:
    """当访问控制表为空且使用 PostgreSQL 时，从种子 SQL 注入菜单/按钮数据。

    - 仅在 `access_control_items` 表为 0 行时执行，避免覆盖用户自定义；
    - 仅针对 PostgreSQL 执行（语句包含 `::jsonb` 与 `setval`）。
    """
    try:
        if db.query(AccessControlItem).first() is not None:
            return
    except Exception:
        # 表不存在等异常直接返回，由 Base.metadata.create_all 负责建表
        return

    # 仅在 PostgreSQL 下执行
    try:
        dialect = db.bind.dialect.name if getattr(db, "bind", None) else None
    except Exception:
        dialect = None
    if dialect != "postgresql":
        return

    from pathlib import Path
    from sqlalchemy import text

    try:
        repo_root = Path(__file__).resolve().parents[4]
        sql_path = repo_root / "scripts" / "db" / "init" / "v1" / "data" / "001_seed_data.sql"
        full_sql = sql_path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Seed SQL file not found or unreadable for access controls: %s", "scripts/db/init/v1/data/001_seed_data.sql")
        return

    # 提取整个 INSERT INTO access_control_items ... VALUES ... ON CONFLICT ...; 语句
    insert_stmt_match = re.search(
        r"INSERT\s+INTO\s+access_control_items\s*\([^;]+?\)\s*VALUES\s*.*?;",
        full_sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not insert_stmt_match:
        return
    insert_stmt = insert_stmt_match.group(0)

    # 提取 setval 对齐语句（若存在）
    setval_match = re.search(
        r"SELECT\s+setval\([^;]+\);",
        full_sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    try:
        db.execute(text(insert_stmt))
        if setval_match:
            db.execute(text(setval_match.group(0)))
        db.flush()
        logger.info("Seeded default access control items from SQL seed file")
    except Exception:
        # 回滚本段，避免影响后续播种
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("Failed to seed access control items from SQL seed file", exc_info=True)


def _seed_default_storage_if_needed(db: Session) -> None:
    """若配置了 LOCAL_FILE_ROOT 且当前无任何存储源，则创建一个默认的本地存储源。

    该逻辑幂等：仅当 storage_configs 为空时触发。
    """
    try:
        if storage_config_crud.count(db) > 0:
            return
        local_root = os.getenv("LOCAL_FILE_ROOT")
        if not local_root:
            return
        cfg = StorageConfig(
            name="本地存储 (默认)",
            type="LOCAL",
            local_root_path=local_root,
            created_by=1,
            organization_id=organization_id if (organization_id := (db.query(Organization.id).filter(Organization.name == DEFAULT_ORGANIZATION_NAME).scalar())) else None,
        )
        db.add(cfg)
        db.flush()
    except Exception:
        # 回滚本次插入失败，避免后续操作出现 PendingRollbackError
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("Failed to seed default local storage from LOCAL_FILE_ROOT", exc_info=True)


def _seed_dictionaries_from_sql_if_needed(db: Session) -> None:
    """在测试或开发环境中，必要时从 SQL 种子脚本注入字典数据。

    - 若已存在典型的字典类型（如 display_status），则认为已完成初始化并跳过；
    - 否则，尝试从 scripts/db/init/v1/data/001_seed_data.sql 中提取针对
      `dictionary_types` 与 `dictionary_entries` 的 INSERT 语句并执行。

    该逻辑为幂等实现，多次执行不会产生重复数据。
    """
    from pathlib import Path
    from sqlalchemy import text

    # 若已存在基础字典类型则跳过
    exists = (
        db.query(DictionaryType)
        .filter(DictionaryType.type_code == "display_status", DictionaryType.is_deleted.is_(False))
        .first()
    )
    if exists is not None:
        return

    # 解析 SQL 文件，仅执行与字典相关的 INSERT 语句
    try:
        repo_root = Path(__file__).resolve().parents[4]  # <repo>/app/packages/system/db -> parents[4] == <repo>
        sql_path = repo_root / "scripts" / "db" / "init" / "v1" / "data" / "001_seed_data.sql"
        sql_text = sql_path.read_text(encoding="utf-8")
    except Exception:  # pragma: no cover - IO 异常仅记录日志
        logger.warning("Seed SQL file not found or unreadable: %s", "scripts/db/init/v1/data/001_seed_data.sql")
        return

    # 解析字典类型
    import re

    from typing import Optional

    def _parse_tuple_values(block: str) -> list[tuple[str, str, Optional[str], int]]:
        # 提取形如 ('a','b','c',1) 的元组序列
        pattern = re.compile(
            r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'(.*?)'\s*,\s*([0-9]+)\s*\)",
            re.DOTALL,
        )
        results: list[tuple[str, str, Optional[str], int]] = []
        for m in pattern.finditer(block):
            type_code = m.group(1)
            display_name = m.group(2)
            description = m.group(3)
            sort_order = int(m.group(4))
            results.append((type_code, display_name, description, sort_order))
        return results

    def _extract_block(src: str, table: str) -> list[str]:
        # 找到 INSERT INTO <table> ... VALUES ...; 可能存在多段（特别是 entries）
        blocks: list[str] = []
        insert_pattern = re.compile(
            rf"INSERT\s+INTO\s+{table}[^;]*?VALUES(.*?);",
            re.IGNORECASE | re.DOTALL,
        )
        for m in insert_pattern.finditer(src):
            blocks.append(m.group(1))
        return blocks

    # 1) 字典类型
    type_blocks = _extract_block(sql_text, "dictionary_types")
    # 获取默认组织 ID 兜底
    default_org_id = None
    try:
        default_org_id = db.query(Organization.id).filter(Organization.name == DEFAULT_ORGANIZATION_NAME).scalar()
    except Exception:
        default_org_id = None

    for block in type_blocks:
        for type_code, display_name, description, sort_order in _parse_tuple_values(block):
            existing = (
                db.query(DictionaryType)
                .filter(DictionaryType.type_code == type_code, DictionaryType.is_deleted.is_(False))
                .first()
            )
            if existing is None:
                db.add(
                    DictionaryType(
                        type_code=type_code,
                        display_name=display_name,
                        description=description,
                        sort_order=sort_order,
                        created_by=1,
                        organization_id=default_org_id or 1,
                    )
                )
    # 确保上面的新增被持久化，后续查询可见
    db.flush()

    # 2) 字典条目：为避免引入模型依赖，这里用原生 SQL 以最小代价 upsert
    #    仅插入不存在的 (type_code, value) 组合
    entry_blocks = _extract_block(sql_text, "dictionary_entries")
    entry_pattern = re.compile(
        r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'(.*?)'\s*,\s*([0-9]+)\s*\)",
        re.DOTALL,
    )
    for block in entry_blocks:
        for m in entry_pattern.finditer(block):
            type_code, label, value, description, sort_order = m.groups()
            sort_order_int = int(sort_order)
            # 仅当类型已存在时才插入条目，维持外键一致性
            type_exists = (
                db.query(DictionaryType)
                .filter(DictionaryType.type_code == type_code, DictionaryType.is_deleted.is_(False))
                .first()
                is not None
            )
            if not type_exists:
                continue
            # 使用方言无关的插入前查询，保证幂等
            # PostgreSQL 布尔应使用 TRUE/FALSE，避免 boolean = integer 报错
            exists_sql = text(
                "SELECT id FROM dictionary_entries WHERE type_code = :type_code AND value = :value AND is_deleted = FALSE"
            )
            row = db.execute(exists_sql, {"type_code": type_code, "value": value}).first()
            if row:
                continue
            insert_sql = text(
                """
                INSERT INTO dictionary_entries (type_code, label, value, description, sort_order, created_by, organization_id, create_time, update_time, is_deleted)
                VALUES (:type_code, :label, :value, :description, :sort_order, :created_by, :organization_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE)
                """
            )
            db.execute(
                insert_sql,
                {
                    "type_code": type_code,
                    "label": label,
                    "value": value,
                    "description": description,
                    "sort_order": sort_order_int,
                    "created_by": 1,
                    "organization_id": default_org_id or 1,
                },
            )
