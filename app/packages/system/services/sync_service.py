"""文件同步服务：扫描存储并将元数据写入数据库。

独立函数形式，避免实例方法绑定导致的 AttributeError 问题。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session
from contextlib import contextmanager, nullcontext

from app.packages.system.core.constants import HTTP_STATUS_OK, HTTP_STATUS_NOT_FOUND, HTTP_STATUS_BAD_REQUEST
from app.packages.system.core.exceptions import AppException
from app.packages.system.core.responses import create_response
from app.packages.system.crud.storage_config import storage_config_crud
from app.packages.system.services.storage_backends import build_backend
from app.packages.system.utils.path_utils import norm_abs_path, norm_dir_key
from app.packages.system.core.logger import logger


def sync_records(db: Session, *, storage_id: int, path: Optional[str] = "/"):
    """扫描指定存储与路径下的文件，并将元数据同步到表 `file_records` 与统一表 `fs_nodes`（目录与文件）。

    - 写入“文件记录”（file_records）和“统一节点”（fs_nodes，目录+文件）；
    - 文件若已存在（以 directory+alias_name 判定），则更新 size/mime；
    - 递归扫描，S3 单层分页限制导致极大目录可能需多次操作；
    - 防御：跳过超长路径（>1024）与超长文件名（>255）的条目；对异常容错并继续。
    """

    cfg = storage_config_crud.get(db, storage_id)
    if cfg is None:
        raise AppException("存储源不存在或已删除", HTTP_STATUS_NOT_FOUND)

    backend = build_backend(
        type=cfg.type,
        region=cfg.region,
        bucket_name=cfg.bucket_name,
        path_prefix=cfg.path_prefix,
        local_root_path=cfg.local_root_path,
        access_key_id=cfg.access_key_id,
        secret_access_key=cfg.secret_access_key,
        endpoint_url=getattr(cfg, "endpoint_url", None),
        custom_domain=getattr(cfg, "custom_domain", None),
        use_https=getattr(cfg, "use_https", True),
        acl_type=getattr(cfg, "acl_type", "private"),
    )

    from app.packages.system.models.file_record import FileRecord
    from app.packages.system.crud.file_record import file_record_crud
    from app.packages.system.crud.fs_node import fs_node_crud

    def _norm_dir(p: str) -> tuple[str, str]:
        raw = (p or "/").strip() or "/"
        if not raw.startswith("/"):
            raw = "/" + raw
        cur = raw if raw.endswith("/") else (raw + "/")
        key = raw.rstrip("/")
        return cur, key

    scanned = 0
    inserted = 0
    updated = 0
    skipped = 0
    visited: set[str] = set()         # 防止递归重复
    visited_dirs: set[str] = set()    # 记录扫描到的目录 path（无尾部/）
    visited_files: set[str] = set()   # 记录扫描到的文件 full path（无尾部/）

    def _walk(cur_path: str) -> None:
        nonlocal scanned, inserted, updated, skipped
        safe_cur = cur_path if cur_path.endswith("/") else (cur_path + "/")
        if safe_cur in visited:
            return
        visited.add(safe_cur)

        try:
            data = backend.list(path=cur_path, file_type=None, search=None)
        except Exception:
            return
        cur_display = data.get("current_path") or (cur_path if cur_path.endswith("/") else (cur_path + "/"))
        _, dir_key = _norm_dir(cur_display)
        for it in data.get("items", []):
            if it.get("type") == "directory":
                name = it.get("name")
                if name in {".thumbnails", "thumbnails"}:
                    continue
                dir_path = f"{cur_display}{name}".rstrip("/")
                visited_dirs.add(dir_path)
                if len(dir_path) > 1024:
                    skipped += 1
                else:
                    try:
                        # fs_nodes 目录写入
                        if fs_node_crud.get_by_path(db, storage_id=storage_id, path=dir_path) is None:
                            base_name = dir_path.rsplit("/", 1)[-1]
                            fs_node_crud.create(db, {"storage_id": storage_id, "path": dir_path, "name": base_name, "is_dir": True})
                    except Exception:
                        skipped += 1
                _walk(f"{cur_display}{name}")
            elif it.get("type") == "file":
                scanned += 1
                name = it.get("name")
                size = int(it.get("size") or 0)
                mime = it.get("mime_type")
                full_path = (f"{dir_key}/{name}" if dir_key else f"/{name}").rstrip("/")
                visited_files.add(full_path)
                if len(f"{dir_key}/{name}") > 1024 or len(name or "") > 255:
                    skipped += 1
                    continue
                try:
                    existing = (
                        file_record_crud
                        .query(db)
                        .filter(FileRecord.storage_id == storage_id)
                        .filter(FileRecord.directory == dir_key)
                        .filter(FileRecord.alias_name == name)
                        .first()
                    )
                    if existing is None:
                        file_record_crud.create(
                            db,
                            {
                                "storage_id": storage_id,
                                "directory": dir_key,
                                "original_name": name,
                                "alias_name": name,
                                "purpose": "general",
                                "size_bytes": size,
                                "mime_type": mime,
                            },
                        )
                        inserted += 1
                        # fs_nodes upsert
                        full_path = (f"{dir_key}/{name}" if dir_key else f"/{name}").rstrip("/")
                        if fs_node_crud.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                            fs_node_crud.create(db, {"storage_id": storage_id, "path": full_path, "name": name, "is_dir": False, "size_bytes": size, "mime_type": mime})
                    else:
                        changed = False
                        if int(existing.size_bytes or 0) != size:
                            existing.size_bytes = size
                            changed = True
                        if (existing.mime_type or None) != (mime or None):
                            existing.mime_type = mime
                            changed = True
                        if changed:
                            file_record_crud.save(db, existing)
                            updated += 1
                        # fs_nodes 更新（若存在）
                        try:
                            full_path = (f"{dir_key}/{name}" if dir_key else f"/{name}").rstrip("/")
                            node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=full_path)
                            if node is not None:
                                node.size_bytes = size
                                node.mime_type = mime
                                fs_node_crud.save(db, node)
                        except Exception:
                            pass
                except Exception:
                    skipped += 1

    cur_display, base_dir_key = _norm_dir(path or "/")
    _walk(cur_display)

    # 确保当前同步根目录不会在清理阶段被误判为“缺失”而软删。
    # 现有逻辑在递归中仅把“子目录”加入 visited_dirs，若对某个子目录执行同步，
    # 其自身（如 /foo）不会被加入 visited_dirs，导致清理阶段 (FsNode.path == '/foo') 命中而被软删，
    # 从父级目录回看便会“消失”。这里在 list 成功时把根目录也加入 visited_dirs 以避免误删。
    try:
        # 若目录真实存在，后续清理应当保留它
        base_prefix_for_dir = cur_display.rstrip("/")  # '/foo/' -> '/foo'
        if base_prefix_for_dir:
            # 仅在后端能列出该目录时，才认定其存在并加入 visited_dirs
            # 注意：_walk 已经尝试过 list，这里再做一次轻量校验以避免边界情况下的误判
            backend.list(path=cur_display)
            visited_dirs.add(base_prefix_for_dir)
    except Exception:
        # 目录不存在/不可访问时，不加入，交由清理逻辑软删
        pass

    # 清理：将 DB 中“扫描范围内但未被发现”的节点软删（仅在 LOCAL 存储启用，避免 S3 分页不完整导致的误删）
    try:
        from app.packages.system.crud.fs_node import fs_node_crud
        from app.packages.system.models.fs_node import FsNode
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.models.file_record import FileRecord

        should_prune = (cfg.type or "").upper() == "LOCAL"
        if should_prune:
            # 规范 prefix：用于匹配子树
            base_prefix = cur_display.rstrip("/")
            # fs_nodes：目录与文件
            qn = fs_node_crud.query(db).filter(FsNode.storage_id == storage_id)
            if base_prefix:
                qn = qn.filter((FsNode.path == base_prefix) | (FsNode.path.like(base_prefix + "/%")))
            else:
                qn = qn.filter(FsNode.path.like("/%"))
            for n in qn.all():
                if n.is_dir:
                    if n.path not in visited_dirs:
                        fs_node_crud.soft_delete(db, n)
                else:
                    if n.path not in visited_files:
                        fs_node_crud.soft_delete(db, n)

            # file_records：仅文件
            qf = file_record_crud.query(db).filter(FileRecord.storage_id == storage_id)
            if base_dir_key != "":
                qf = qf.filter((FileRecord.directory == base_dir_key) | (FileRecord.directory.like(base_dir_key + "/%")))
            # 否则 base_dir_key == '' -> 全部
            for fr in qf.all():
                full_path = (f"/{fr.alias_name}" if (fr.directory or "") == "" else f"{fr.directory}/{fr.alias_name}")
                if full_path not in visited_files:
                    file_record_crud.soft_delete(db, fr)
    except Exception:
        # 防御：清理异常不阻断主流程
        pass

    return create_response(
        "同步完成",
        {"scanned": scanned, "inserted": inserted, "updated": updated, "skipped": skipped},
        HTTP_STATUS_OK,
    )


def sync_delete_records(db: Session, *, storage_id: int, paths: list[str]) -> dict:
    """仅同步数据库的删除（配合已完成的存储删除）。返回删除统计。

    说明：
    - 与 FileService._sync_delete_in_db 等效，但以顶层函数形式提供，避免实例方法差异导致的调用失败；
    - 使用硬删（失败兜底软删），确保列表立刻反映变更；
    - 直接使用 db.query(...)，不受数据域过滤影响。
    """
    from app.packages.system.crud.file_record import file_record_crud
    from app.packages.system.models.file_record import FileRecord
    from app.packages.system.crud.fs_node import fs_node_crud
    from app.packages.system.models.fs_node import FsNode

    try:
        logger.info("sync_delete(top).start storage_id=%s paths_in=%s", storage_id, paths)
    except Exception:
        pass

    files_deleted = 0
    nodes_deleted = 0

    def _norm(p: str) -> str:
        s = (p or "/").strip()
        if not s.startswith("/"):
            s = "/" + s
        return s

    # Use a transaction helper that works even if Session already has an implicit txn
    @contextmanager
    def _tx(db: Session):
        """Provide a commit/rollback boundary that tolerates an already-begun Session.

        Some FastAPI requests may trigger an implicit BEGIN on the shared Session
        (e.g. prior SELECTs by other dependencies). Calling ``Session.begin()``
        again would raise ``InvalidRequestError: A transaction is already begun``.
        This helper detects that state and, instead of nesting ``begin()``,
        runs the block and then explicitly commits/rolls back the outer txn.
        """
        has_tx = False
        try:
            has_tx = bool(getattr(db, "in_transaction", lambda: False)())
        except Exception:
            try:
                has_tx = getattr(db, "get_transaction", lambda: lambda: None)() is not None
            except Exception:
                has_tx = False
        if has_tx:
            try:
                yield
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                raise
        else:
            with db.begin():
                yield

    with _tx(db):
        for raw in (paths or []):
            p = _norm(raw)
            parent = p.rsplit("/", 1)[0]
            name = p.rsplit("/", 1)[1] if "/" in p else p
            dir_key = parent.rstrip("/")
            if dir_key == "/":
                dir_key = ""

            # 文件记录：严格匹配 directory + alias_name
            try:
                q = (
                    db.query(FileRecord)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == dir_key)
                    .filter(FileRecord.alias_name == name)
                )
                for row in q.all():
                    try:
                        file_record_crud.hard_delete(db, row, auto_commit=False)
                        files_deleted += 1
                    except Exception:
                        file_record_crud.soft_delete(db, row, auto_commit=False)
                        files_deleted += 1
            except Exception:
                pass

            # 统一表：单文件节点
            try:
                node = db.query(FsNode).filter(FsNode.storage_id == storage_id, FsNode.path == p.rstrip("/")).first()
                if node is not None:
                    try:
                        fs_node_crud.hard_delete(db, node, auto_commit=False)
                        nodes_deleted += 1
                    except Exception:
                        fs_node_crud.soft_delete(db, node, auto_commit=False)
                        nodes_deleted += 1
            except Exception:
                pass

            # 目录前缀删
            try:
                p_norm = p.rstrip("/")
                if p_norm and p_norm != "/":
                    q_files = (
                        db.query(FileRecord)
                        .filter(FileRecord.storage_id == storage_id)
                        .filter((FileRecord.directory == p_norm) | (FileRecord.directory.like(p_norm + "/%")))
                    )
                    for fr in q_files.all():
                        try:
                            file_record_crud.hard_delete(db, fr, auto_commit=False)
                            files_deleted += 1
                        except Exception:
                            file_record_crud.soft_delete(db, fr, auto_commit=False)
                            files_deleted += 1

                    qn = (
                        db.query(FsNode)
                        .filter(FsNode.storage_id == storage_id)
                        .filter((FsNode.path == p_norm) | (FsNode.path.like(p_norm + "/%")))
                    )
                    for n in qn.all():
                        try:
                            fs_node_crud.hard_delete(db, n, auto_commit=False)
                            nodes_deleted += 1
                        except Exception:
                            fs_node_crud.soft_delete(db, n, auto_commit=False)
                            nodes_deleted += 1
            except Exception:
                pass

    result = {"filesDeleted": files_deleted, "nodesDeleted": nodes_deleted}
    try:
        logger.info("sync_delete(top).done storage_id=%s result=%s", storage_id, result)
    except Exception:
        pass
    return result


def _norm_abs_path(p: str) -> str:
    return norm_abs_path(p)


def _norm_dir_key(p: str) -> str:
    return norm_dir_key(p)


def sync_rename_records(
    db: Session,
    *,
    storage_id: int,
    old_path: str,
    new_path: str,
) -> dict:
    """在存储层完成重命名后，同步数据库元数据（file_records 与 fs_nodes）。

    - 目录重命名：对目录前缀进行批量替换；确保目标目录节点存在；
    - 文件重命名：更新单条记录的 directory + alias_name；若源记录不存在，
      从目标父目录列一次补写 size/mime；同时更新/补写统一表 fs_nodes。
    返回：{"dirsRenamed": int, "filesRenamed": int}
    """
    from app.packages.system.crud.file_record import file_record_crud
    from app.packages.system.models.file_record import FileRecord
    from app.packages.system.crud.fs_node import fs_node_crud
    from app.packages.system.models.fs_node import FsNode

    dirs_renamed = 0
    files_renamed = 0

    old_abs = _norm_abs_path(old_path)
    new_abs = _norm_abs_path(new_path)

    # 判定是否目录：优先依据 fs_nodes，其次尾斜杠语义
    is_dir = False
    try:
        node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=old_abs.rstrip("/"))
        is_dir = bool(node and getattr(node, "is_dir", False))
    except Exception:
        is_dir = False
    if not is_dir:
        is_dir = old_abs.endswith("/") or new_abs.endswith("/")

    def ensure_dir_entry(dir_path: str) -> None:
        key = dir_path.rstrip("/")
        if key == "/":
            return
        node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=key)
        if node is None:
            base_name = key.rsplit("/", 1)[-1]
            fs_node_crud.create(db, {"storage_id": storage_id, "path": key, "name": base_name, "is_dir": True}, auto_commit=False)
            try:
                db.flush()
            except Exception:
                pass

    if is_dir:
        # 目录：批量前缀替换
        src_dir = old_abs.rstrip("/")
        dst_dir = new_abs.rstrip("/")
        # 仅确保目标父目录存在，避免预创建 dst_dir 与后续“将 src 节点更新为 dst”产生唯一约束冲突
        dst_parent = dst_dir.rsplit("/", 1)[0] if "/" in dst_dir else "/"
        ensure_dir_entry(dst_parent or "/")
        try:
            qf = (
                db.query(FileRecord)
                .filter(FileRecord.storage_id == storage_id)
                .filter((FileRecord.directory == src_dir) | (FileRecord.directory.like(src_dir + "/%")))
            )
            for f in qf.all():
                if f.directory == src_dir:
                    f.directory = dst_dir
                elif f.directory.startswith(src_dir + "/"):
                    f.directory = dst_dir + f.directory[len(src_dir):]
                file_record_crud.save(db, f, auto_commit=False)
        except Exception:
            pass
        try:
            qn = (
                db.query(FsNode)
                .filter(FsNode.storage_id == storage_id)
                .filter((FsNode.path == src_dir) | (FsNode.path.like(src_dir + "/%")))
            )
            for n in qn.all():
                if n.path == src_dir:
                    n.path = dst_dir
                elif n.path.startswith(src_dir + "/"):
                    n.path = dst_dir + n.path[len(src_dir):]
                n.name = n.path.rsplit("/", 1)[-1]
                fs_node_crud.save(db, n, auto_commit=False)
        except Exception:
            pass
        try:
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        dirs_renamed = 1
    else:
        # 文件：更新 single record + fs_node
        src_parent = old_abs.rsplit("/", 1)[0]
        src_name = old_abs.rsplit("/", 1)[1]
        dst_parent = new_abs.rsplit("/", 1)[0]
        dst_name = new_abs.rsplit("/", 1)[1]

        ensure_dir_entry(dst_parent)
        matched = False
        try:
            q = (
                db.query(FileRecord)
                .filter(FileRecord.storage_id == storage_id)
                .filter(FileRecord.directory == _norm_dir_key(src_parent))
                .filter(FileRecord.alias_name == src_name)
            )
            for row in q.all():
                row.directory = _norm_dir_key(dst_parent)
                row.alias_name = dst_name
                file_record_crud.save(db, row, auto_commit=False)
                matched = True
        except Exception:
            pass

        # 更新/补写 fs_node
        try:
            src_full = old_abs.rstrip("/")
            dst_full = f"{dst_parent}/{dst_name}".rstrip("/")
            node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=src_full)
            if node is not None:
                node.path = dst_full
                node.name = dst_name
                fs_node_crud.save(db, node, auto_commit=False)
            else:
                if fs_node_crud.get_by_path(db, storage_id=storage_id, path=dst_full) is None:
                    fs_node_crud.create(db, {"storage_id": storage_id, "path": dst_full, "name": dst_name, "is_dir": False}, auto_commit=False)
        except Exception:
            pass

        if not matched:
            # 目标父目录 list 一次补写 size/mime
            size_v = 0
            mime_v = None
            try:
                cfg = storage_config_crud.get(db, storage_id)
                backend = build_backend(
                    type=cfg.type,
                    region=cfg.region,
                    bucket_name=cfg.bucket_name,
                    path_prefix=cfg.path_prefix,
                    local_root_path=cfg.local_root_path,
                    access_key_id=cfg.access_key_id,
                    secret_access_key=cfg.secret_access_key,
                    endpoint_url=getattr(cfg, "endpoint_url", None),
                    custom_domain=getattr(cfg, "custom_domain", None),
                    use_https=getattr(cfg, "use_https", True),
                    acl_type=getattr(cfg, "acl_type", "private"),
                )
                listing = backend.list(path=dst_parent)
                for it in listing.get("items", []) or []:
                    if it.get("type") == "file" and (it.get("name") or "") == dst_name:
                        size_v = int(it.get("size") or 0)
                        mime_v = it.get("mime_type")
                        break
            except Exception:
                pass
            try:
                file_record_crud.create(
                    db,
                    {
                        "storage_id": storage_id,
                        "directory": _norm_dir_key(dst_parent),
                        "original_name": dst_name,
                        "alias_name": dst_name,
                        "purpose": "general",
                        "size_bytes": size_v,
                        "mime_type": mime_v,
                    },
                    auto_commit=False,
                )
            except Exception:
                pass
        try:
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        files_renamed = 1

    return {"dirsRenamed": dirs_renamed, "filesRenamed": files_renamed}

def sync_move_records(
    db: Session,
    *,
    storage_id: int,
    source_paths: list[str],
    destination_path: str,
) -> dict:
    """存储层移动后，同步 DB 元数据（目录/文件）。返回统计。

    - 目录：前缀替换 file_records 与 fs_nodes；确保目标目录节点存在；
    - 文件：更新单条记录目录与 fs_node.path；若源记录不在 DB，则从目标父目录 list 一次补写 size/mime。
    """
    from app.packages.system.crud.file_record import file_record_crud
    from app.packages.system.models.file_record import FileRecord
    from app.packages.system.crud.fs_node import fs_node_crud
    from app.packages.system.models.fs_node import FsNode
    from app.packages.system.crud.fs_node import fs_node_crud as _fs

    moved_files = 0
    moved_dirs = 0

    dst_base = _norm_abs_path(destination_path).rstrip("/")

    def ensure_dir_entry(dir_path: str) -> None:
        key = dir_path.rstrip("/")
        if key == "/":
            return
        node = _fs.get_by_path(db, storage_id=storage_id, path=key)
        if node is None:
            base_name = key.rsplit("/", 1)[-1]
            # keep inside current transaction boundary; flush so later queries can see it
            _fs.create(db, {"storage_id": storage_id, "path": key, "name": base_name, "is_dir": True}, auto_commit=False)
            try:
                db.flush()
            except Exception:
                pass

    # Tolerate an already-begun Session (implicit BEGIN from prior selects)
    @contextmanager
    def _tx(db: Session):
        has_tx = False
        try:
            has_tx = bool(getattr(db, "in_transaction", lambda: False)())
        except Exception:
            try:
                has_tx = getattr(db, "get_transaction", lambda: lambda: None)() is not None
            except Exception:
                has_tx = False
        if has_tx:
            try:
                yield
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                raise
        else:
            with db.begin():
                yield

    with _tx(db):
        for spath in (source_paths or []):
            src_abs = _norm_abs_path(spath)
        base_name = src_abs.rstrip("/").rsplit("/", 1)[-1]
        # 判定是否目录：优先 fs_nodes
        try:
            node = _fs.get_by_path(db, storage_id=storage_id, path=src_abs.rstrip("/"))
            is_dir = bool(node and getattr(node, "is_dir", False))
        except Exception:
            is_dir = False
        if not is_dir and src_abs.endswith("/"):
            is_dir = True

        if is_dir:
            src_dir = src_abs.rstrip("/")
            dst_dir = f"{dst_base}/{base_name}"
            # Moving a directory: do NOT pre-create the destination directory node,
            # otherwise updating src node to the same path will hit unique constraint.
            # We only ensure the destination parent exists for consistent tree.
            ensure_dir_entry(dst_base)
            # file_records 前缀替换
            try:
                qf = (
                    db.query(FileRecord)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter((FileRecord.directory == src_dir) | (FileRecord.directory.like(src_dir + "/%")))
                )
                for f in qf.all():
                    if f.directory == src_dir:
                        f.directory = dst_dir
                    elif f.directory.startswith(src_dir + "/"):
                        f.directory = dst_dir + f.directory[len(src_dir):]
                    file_record_crud.save(db, f, auto_commit=False)
            except Exception:
                pass
            # fs_nodes 前缀替换
            try:
                qn = (
                    db.query(FsNode)
                    .filter(FsNode.storage_id == storage_id)
                    .filter((FsNode.path == src_dir) | (FsNode.path.like(src_dir + "/%")))
                )
                for n in qn.all():
                    if n.path == src_dir:
                        n.path = dst_dir
                    elif n.path.startswith(src_dir + "/"):
                        n.path = dst_dir + n.path[len(src_dir):]
                    n.name = n.path.rsplit("/", 1)[-1]
                    fs_node_crud.save(db, n, auto_commit=False)
            except Exception:
                pass
            moved_dirs += 1
        else:
            # 单文件
            src_parent = src_abs.rsplit("/", 1)[0]
            name = src_abs.rsplit("/", 1)[1]
            dst_parent = dst_base
            ensure_dir_entry(dst_parent)

            try:
                q = (
                    db.query(FileRecord)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == _norm_dir_key(src_parent))
                    .filter(FileRecord.alias_name == name)
                )
                matched = False
                for row in q.all():
                    row.directory = _norm_dir_key(dst_parent)
                    file_record_crud.save(db, row, auto_commit=False)
                    matched = True
                # 同步 fs_nodes
                try:
                    src_full = src_abs.rstrip("/")
                    dst_full = f"{dst_base}/{name}"
                    node = _fs.get_by_path(db, storage_id=storage_id, path=src_full)
                    if node is not None:
                        node.path = dst_full
                        node.name = name
                        fs_node_crud.save(db, node, auto_commit=False)
                except Exception:
                    pass
                if not matched:
                    # 目标父目录 list 一次补写记录（构造后端获取 size/mime）
                    from app.packages.system.crud.storage_config import storage_config_crud
                    cfg = storage_config_crud.get(db, storage_id)
                    size_v = 0
                    mime_v = None
                    try:
                        backend = build_backend(
                            type=cfg.type,
                            region=cfg.region,
                            bucket_name=cfg.bucket_name,
                            path_prefix=cfg.path_prefix,
                            local_root_path=cfg.local_root_path,
                            access_key_id=cfg.access_key_id,
                            secret_access_key=cfg.secret_access_key,
                            endpoint_url=getattr(cfg, "endpoint_url", None),
                            custom_domain=getattr(cfg, "custom_domain", None),
                            use_https=getattr(cfg, "use_https", True),
                            acl_type=getattr(cfg, "acl_type", "private"),
                        )
                        listing = backend.list(path=dst_parent)
                        for it in listing.get("items", []) or []:
                            if it.get("type") == "file" and (it.get("name") or "") == name:
                                size_v = int(it.get("size") or 0)
                                mime_v = it.get("mime_type")
                                break
                    except Exception:
                        pass
                    file_record_crud.create(
                        db,
                        {
                            "storage_id": storage_id,
                            "directory": _norm_dir_key(dst_parent),
                            "original_name": name,
                            "alias_name": name,
                            "purpose": "general",
                            "size_bytes": size_v,
                            "mime_type": mime_v,
                        },
                        auto_commit=False,
                    )
                    # fs_node upsert
                    try:
                        full_path = f"{dst_parent}/{name}".rstrip("/")
                        if _fs.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                            _fs.create(db, {
                                "storage_id": storage_id,
                                "path": full_path,
                                "name": name,
                                "is_dir": False,
                                "size_bytes": size_v,
                                "mime_type": mime_v,
                            }, auto_commit=False)
                    except Exception:
                        pass
            except Exception:
                pass
            moved_files += 1

    return {"filesMoved": moved_files, "dirsMoved": moved_dirs}


def sync_copy_records(
    db: Session,
    *,
    storage_id: int,
    source_paths: list[str],
    destination_path: str,
) -> dict:
    """存储层复制后，同步 DB 元数据（目录/文件）。返回统计。

    - 目录：复制 fs_nodes 子树与 file_records（前缀替换）；若源目录无 DB 记录，回退对子树做微同步；
    - 文件：复制单条记录，若源文件不在 DB，则在目标父目录补写记录并 upsert fs_node。
    """
    from app.packages.system.crud.file_record import file_record_crud
    from app.packages.system.models.file_record import FileRecord
    from app.packages.system.crud.fs_node import fs_node_crud
    from app.packages.system.models.fs_node import FsNode
    from app.packages.system.crud.fs_node import fs_node_crud as _fs

    copied_files = 0
    copied_dirs = 0
    # Track paths we create within this transaction to avoid duplicate inserts
    created_node_paths: set[str] = set()

    dst_base = _norm_abs_path(destination_path).rstrip("/")

    def ensure_dir_entry(dir_path: str) -> None:
        key = dir_path.rstrip("/")
        if key == "/":
            return
        if key in created_node_paths:
            return
        node = _fs.get_by_path(db, storage_id=storage_id, path=key)
        if node is None:
            base_name = key.rsplit("/", 1)[-1]
            # keep inside current transaction boundary; flush so later queries can see it
            _fs.create(db, {"storage_id": storage_id, "path": key, "name": base_name, "is_dir": True}, auto_commit=False)
            try:
                db.flush()
            except Exception:
                pass
            created_node_paths.add(key)

    # Tolerate an already-begun Session (implicit BEGIN from prior selects)
    @contextmanager
    def _tx_copy(db: Session):
        has_tx = False
        try:
            has_tx = bool(getattr(db, "in_transaction", lambda: False)())
        except Exception:
            try:
                has_tx = getattr(db, "get_transaction", lambda: lambda: None)() is not None
            except Exception:
                has_tx = False
        if has_tx:
            try:
                yield
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                raise
        else:
            with db.begin():
                yield

    with _tx_copy(db):
        for spath in (source_paths or []):
            src_abs = _norm_abs_path(spath)
        base_name = src_abs.rstrip("/").rsplit("/", 1)[-1]
        # 判定是否目录
        try:
            node = _fs.get_by_path(db, storage_id=storage_id, path=src_abs.rstrip("/"))
            is_dir = bool(node and getattr(node, "is_dir", False))
        except Exception:
            is_dir = False
        if not is_dir and src_abs.endswith("/"):
            is_dir = True

        if is_dir:
            src_dir = src_abs.rstrip("/")
            dst_dir = f"{dst_base}/{base_name}"
            # Copying a directory: do NOT pre-create dst_dir to avoid duplicate with subtree copy; ensure parent only.
            ensure_dir_entry(dst_base)
            # 复制 fs_nodes 子树
            copied_any = False
            try:
                qn = (
                    db.query(FsNode)
                    .filter(FsNode.storage_id == storage_id)
                    .filter((FsNode.path == src_dir) | (FsNode.path.like(src_dir + "/%")))
                )
                for n in qn.all():
                    suffix = n.path[len(src_dir):]
                    new_path = (dst_dir + suffix).rstrip("/")
                    if new_path not in created_node_paths and _fs.get_by_path(db, storage_id=storage_id, path=new_path) is None:
                        _fs.create(db, {"storage_id": storage_id, "path": new_path, "name": new_path.rsplit("/", 1)[-1], "is_dir": n.is_dir, "size_bytes": int(n.size_bytes or 0), "mime_type": n.mime_type}, auto_commit=False)
                        copied_any = True
                        created_node_paths.add(new_path)
                # flush created fs_nodes so that later queries can see them and avoid dup inserts
                if copied_any:
                    try:
                        db.flush()
                    except Exception:
                        pass
            except Exception:
                pass
            # 复制 file_records
            try:
                qf = (
                    db.query(FileRecord)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter((FileRecord.directory == src_dir) | (FileRecord.directory.like(src_dir + "/%")))
                )
                had = False
                for f in qf.all():
                    suffix = f.directory[len(src_dir):]
                    new_dir = (dst_dir + suffix).rstrip("/")
                    file_record_crud.create(
                        db,
                        {
                            "storage_id": storage_id,
                            "directory": new_dir,
                            "original_name": f.original_name,
                            "alias_name": f.alias_name,
                            "purpose": f.purpose,
                            "size_bytes": f.size_bytes,
                            "mime_type": f.mime_type,
                        }, auto_commit=False,
                    )
                    had = True
                    copied_files += 1
                    # upsert fs_node
                    try:
                        full_path = (f"{new_dir}/{f.alias_name}" if new_dir else f"/{f.alias_name}").rstrip("/")
                        if full_path not in created_node_paths and _fs.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                            _fs.create(db, {"storage_id": storage_id, "path": full_path, "name": f.alias_name, "is_dir": False, "size_bytes": int(f.size_bytes or 0), "mime_type": f.mime_type}, auto_commit=False)
                            created_node_paths.add(full_path)
                    except Exception:
                        pass
                if had:
                    copied_dirs += 1
            except Exception:
                pass
            # 若源目录在 DB 中没有任何记录，微同步目标子树
            if not copied_any:
                try:
                    sync_records(db, storage_id=storage_id, path=dst_dir + "/")
                except Exception:
                    pass
        else:
            # 文件复制
            src_parent = src_abs.rsplit("/", 1)[0]
            name = src_abs.rsplit("/", 1)[1]
            ensure_dir_entry(dst_base)
            try:
                row = (
                    db.query(FileRecord)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == _norm_dir_key(src_parent))
                    .filter(FileRecord.alias_name == name)
                    .first()
                )
                if row is not None:
                    file_record_crud.create(
                        db,
                        {
                            "storage_id": storage_id,
                            "directory": _norm_dir_key(dst_base),
                            "original_name": row.original_name,
                            "alias_name": row.alias_name,
                            "purpose": row.purpose,
                            "size_bytes": row.size_bytes,
                            "mime_type": row.mime_type,
                        }, auto_commit=False,
                    )
                    # upsert fs_node
                    try:
                        new_dir = _norm_dir_key(dst_base)
                        full_path = (f"{new_dir}/{row.alias_name}" if new_dir else f"/{row.alias_name}").rstrip("/")
                        if _fs.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                            _fs.create(db, {"storage_id": storage_id, "path": full_path, "name": row.alias_name, "is_dir": False, "size_bytes": int(row.size_bytes or 0), "mime_type": row.mime_type}, auto_commit=False)
                    except Exception:
                        pass
                else:
                    # 源文件不在 DB，也要尽量补齐目标侧记录
                    file_record_crud.create(
                        db,
                        {
                            "storage_id": storage_id,
                            "directory": _norm_dir_key(dst_base),
                            "original_name": name,
                            "alias_name": name,
                            "purpose": "general",
                            "size_bytes": 0,
                            "mime_type": None,
                        }, auto_commit=False,
                    )
                    try:
                        full_path = f"{dst_base}/{name}".rstrip("/")
                        if _fs.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                            _fs.create(db, {"storage_id": storage_id, "path": full_path, "name": name, "is_dir": False, "size_bytes": 0, "mime_type": None}, auto_commit=False)
                    except Exception:
                        pass
                copied_files += 1
            except Exception:
                pass

    return {"filesCopied": copied_files, "dirsCopied": copied_dirs}
