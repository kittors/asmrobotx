"""文件操作服务：基于存储源配置执行各类文件/文件夹操作。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import os
import mimetypes

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.packages.system.core.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from app.packages.system.core.exceptions import AppException
from app.packages.system.core.responses import create_response
from app.packages.system.crud.storage_config import storage_config_crud
from app.packages.system.services.storage_backends import build_backend


class FileService:
    def _get_backend(self, db: Session, *, storage_id: int):
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
        return backend

    # ----------------------------
    # 查询
    # ----------------------------
    def list_items(
        self,
        db: Session,
        *,
        storage_id: int,
        path: Optional[str] = "/",
        file_type: Optional[str] = None,
        search: Optional[str] = None,
        # 分页/排序参数（可选）
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include: Optional[str] = None,
        order_by: Optional[str] = None,
        order: Optional[str] = None,
        count_only: bool = False,
    ) -> Dict[str, Any]:
        # 若提供了分页/排序/计数参数，则走新的分页逻辑；否则保持旧结构以兼容现有前端/测试
        if any(
            x is not None
            for x in (
                limit,
                cursor,
                include,
                order_by,
                order,
            )
        ) or count_only:
            return self._list_items_paged(
                db,
                storage_id=storage_id,
                path=path,
                file_type=file_type,
                search=search,
                limit=limit,
                cursor=cursor,
                include=include,
                order_by=order_by,
                order=order,
                count_only=count_only,
            )
        """严格基于数据库返回文件列表。

        - 仅从表 `file_records` 读取，不触达对象存储或本地文件系统；
        - `fileType` 仅影响“文件”项的过滤；当提供且不为 `all` 时，不返回目录；
        - `search` 同时匹配目录名与文件名（original/alias）。
        """

        # 延迟导入，避免循环依赖
        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.crud.storage_config import storage_config_crud

        # 统一归一化：展示用 current_path 始终以 '/' 结尾；查询用 dir_key 不以 '/' 结尾（根目录为空字符串）
        raw_path = (path or "/").strip() or "/"
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
        current_path = raw_path if raw_path.endswith("/") else (raw_path + "/")
        dir_key = raw_path.rstrip("/")  # root -> ""

        # 过滤器准备
        search_lower = (search or "").strip().lower()

        def _is_allowed_type(name: str) -> bool:
            if not file_type or file_type == "all":
                return True
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            groups = {
                "image": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp"},
                "document": {"doc", "docx", "odt"},
                "spreadsheet": {"xls", "xlsx", "ods"},
                "pdf": {"pdf"},
                "markdown": {"md"},
            }
            allowed = groups.get(file_type)
            return True if allowed is None else (ext in allowed)

        items: list[dict] = []

        # 1) 目录（仅当 file_type 未限定为某类文件时返回）
        if not file_type or file_type == "all":
            # 取出以当前路径为前缀的所有目录，提取“直接子目录”名
            # 注意：FileRecord.directory 不包含尾部 '/'，根目录存空字符串
            prefix = (dir_key + "/") if dir_key else "/"
            # 仅取目录字段，去重
            q_dirs = (
                file_record_crud
                .query(db)
                .filter(FileRecord.storage_id == storage_id)
                .filter(FileRecord.directory.like(prefix + "%"))
                .with_entities(FileRecord.directory)
                .distinct()
            )
            # 目录表中的路径，同样参与集合
            try:
                from app.packages.system.models.directory_entry import DirectoryEntry
                from app.packages.system.crud.directory_entry import directory_entry_crud
                q_dir_entries = (
                    directory_entry_crud
                    .query(db)
                    .filter(DirectoryEntry.storage_id == storage_id)
                    .filter(DirectoryEntry.path.like(prefix + "%"))
                    .with_entities(DirectoryEntry.path)
                    .distinct()
                )
            except Exception:
                q_dir_entries = []
            child_names: set[str] = set()
            for (d,) in q_dirs:  # each row is a tuple (directory,)
                d = d or ""  # 防御：None/""
                # 必须以 prefix 起始才是子路径
                if not (d + "/").startswith(prefix):
                    continue
                # 取出 prefix 之后的第一段作为“直接子目录”
                rel = (d + "/")[len(prefix) :]  # 始终有末尾 '/'
                name = rel.split("/", 1)[0].strip()
                if not name:
                    continue
                if search_lower and search_lower not in name.lower():
                    continue
                child_names.add(name)

            # 合并目录表中的路径
            try:
                for (p,) in q_dir_entries:  # each row is (path,)
                    p = p or ""
                    if not p:
                        continue
                    # 目录表 path 存储不带末尾 '/'
                    if not (p + "/").startswith(prefix):
                        continue
                    rel = (p + "/")[len(prefix) :]
                    name = rel.split("/", 1)[0].strip()
                    if not name:
                        continue
                    if search_lower and search_lower not in name.lower():
                        continue
                    child_names.add(name)
            except Exception:
                pass

            for name in sorted(child_names, key=lambda s: s.lower()):
                items.append(
                    {
                        "name": name,
                        "type": "directory",
                        "mimeType": None,
                        "size": 0,
                        "lastModified": None,
                    }
                )

        # 2) 当前目录下的文件
        q_files_base = (
            file_record_crud
            .query(db)
            .filter(FileRecord.storage_id == storage_id)
        )
        if dir_key == "":
            q_files = q_files_base.filter(FileRecord.directory == "")
        else:
            q_files = q_files_base.filter(FileRecord.directory == dir_key)
        # search 同时匹配 original_name 与 alias_name
        rows = q_files.all()
        for r in rows:
            name = r.alias_name or r.original_name
            if search_lower:
                hay = f"{(r.original_name or '').lower()}\n{(r.alias_name or '').lower()}"
                if search_lower not in hay:
                    continue
            if not _is_allowed_type(name):
                continue
            file_item = {
                "name": name,
                "type": "file",
                "mimeType": r.mime_type,
                "size": int(r.size_bytes or 0),
                "lastModified": (getattr(r, "update_time", None) or getattr(r, "create_time", None)).isoformat() if getattr(r, "create_time", None) else None,
                "previewUrl": f"/api/v1/files/preview?storageId={storage_id}&path={current_path}{name}",
            }
            # 图片提供缩略图 URL（默认 256）
            mime_lc = (r.mime_type or "").lower()
            if mime_lc.startswith("image/"):
                file_item["thumbnailUrl"] = f"/api/v1/files/thumbnail?storageId={storage_id}&path={current_path}{name}&w=256"
            items.append(file_item)

        # 若为本地存储，额外返回根目录绝对路径（currentPath 仍保持相对路径样式）
        root_path: Optional[str] = None
        try:
            cfg = storage_config_crud.get(db, storage_id)
            if cfg and (cfg.type or "").upper() == "LOCAL" and cfg.local_root_path:
                root_path = os.path.abspath(cfg.local_root_path)
        except Exception:
            pass

        payload = {"currentPath": current_path, "items": items}
        if root_path:
            payload["rootPath"] = root_path
        return create_response("获取文件列表成功", payload, HTTP_STATUS_OK)

    # ----------------------------
    # 分页版列表（目录/文件分区分页）
    # ----------------------------
    def _list_items_paged(
        self,
        db: Session,
        *,
        storage_id: int,
        path: Optional[str],
        file_type: Optional[str],
        search: Optional[str],
        limit: Optional[int],
        cursor: Optional[str],
        include: Optional[str],
        order_by: Optional[str],
        order: Optional[str],
        count_only: bool,
    ) -> Dict[str, Any]:
        import base64, json
        from sqlalchemy import func, and_, or_, not_

        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.file_record import file_record_crud

        # 归一化路径
        raw_path = (path or "/").strip() or "/"
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
        current_path = raw_path if raw_path.endswith("/") else (raw_path + "/")
        dir_key = raw_path.rstrip("/")

        # 参数与默认
        part = (include or "all").lower()
        lmt = int(limit or 50)
        ob = (order_by or "name").lower()
        od = (order or "asc").lower()
        od_asc = od == "asc"

        def _encode_cursor(payload: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

        def _decode_cursor(c: Optional[str]) -> Optional[dict]:
            if not c:
                return None
            try:
                return json.loads(base64.urlsafe_b64decode(c.encode("ascii")).decode("utf-8"))
            except Exception:
                raise AppException("cursor 非法", HTTP_STATUS_BAD_REQUEST)

        # counts-only 模式
        if count_only:
            dir_count = self._count_directories(db, storage_id=storage_id, current_path=current_path)
            file_count = self._count_files(db, storage_id=storage_id, dir_key=dir_key, search=search, file_type=file_type)
            payload = {"currentPath": current_path, "counts": {"dirCount": dir_count, "fileCount": file_count}}
            try:
                cfg = storage_config_crud.get(db, storage_id)
                if cfg and (cfg.type or "").upper() == "LOCAL" and cfg.local_root_path:
                    payload["rootPath"] = os.path.abspath(cfg.local_root_path)
            except Exception:
                pass
            return create_response("获取文件数量成功", payload, HTTP_STATUS_OK)

        result: dict = {"currentPath": current_path}
        # rootPath（LOCAL）
        try:
            cfg = storage_config_crud.get(db, storage_id)
            if cfg and (cfg.type or "").upper() == "LOCAL" and cfg.local_root_path:
                result["rootPath"] = os.path.abspath(cfg.local_root_path)
        except Exception:
            pass

        # directories 分页
        if part in ("all", "dirs"):
            dirs_page = self._page_directories(db, storage_id=storage_id, current_path=current_path, limit=lmt, cursor=_decode_cursor(cursor) if part == "dirs" else None)
            result["directories"] = dirs_page

        # files 分页
        if part in ("all", "files"):
            files_page = self._page_files(
                db,
                storage_id=storage_id,
                dir_key=dir_key,
                search=search,
                file_type=file_type,
                limit=lmt,
                cursor=_decode_cursor(cursor) if part == "files" else None,
                order_by=ob,
                order_asc=od_asc,
                current_path=current_path,
            )
            result["files"] = files_page

        # 兼容：补充 items（旧前端/测试使用），按“目录在前，文件在后”拼接当前页
        combined: list[dict] = []
        if "directories" in result and part in ("all", "dirs"):
            combined.extend(result["directories"].get("items") or [])
        if "files" in result and part in ("all", "files"):
            combined.extend(result["files"].get("items") or [])
        result["items"] = combined

        return create_response("获取文件列表成功", result, HTTP_STATUS_OK)

    def _count_directories(self, db: Session, *, storage_id: int, current_path: str) -> int:
        from app.packages.system.models.directory_entry import DirectoryEntry
        from app.packages.system.crud.directory_entry import directory_entry_crud
        prefix = current_path
        q = (
            directory_entry_crud
            .query(db)
            .filter(DirectoryEntry.storage_id == storage_id)
            .filter(DirectoryEntry.path.like(prefix + "%"))
            .filter(not_(DirectoryEntry.path.like(prefix + "%/%")))
            .filter(not_(DirectoryEntry.path.like("/.thumbnails%")))
            .filter(not_(DirectoryEntry.path.like("/thumbnails%")))
        )
        return q.count()

    def _count_files(self, db: Session, *, storage_id: int, dir_key: str, search: Optional[str], file_type: Optional[str]) -> int:
        from sqlalchemy import func
        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.file_record import file_record_crud

        q = (
            file_record_crud
            .query(db)
            .filter(FileRecord.storage_id == storage_id)
            .filter(FileRecord.directory == ("" if dir_key == "" else dir_key))
        )
        if search:
            s = f"%{search.lower()}%"
            q = q.filter(or_(func.lower(FileRecord.alias_name).like(s), func.lower(FileRecord.original_name).like(s)))
        if file_type and file_type != "all":
            # 简易按扩展过滤
            exts = {
                "image": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp"},
                "document": {"doc", "docx", "odt"},
                "spreadsheet": {"xls", "xlsx", "ods"},
                "pdf": {"pdf"},
                "markdown": {"md"},
            }.get(file_type)
            if exts:
                patterns = tuple(f"%.{e}" for e in exts)
                q = q.filter(or_(*[FileRecord.alias_name.ilike(p) for p in patterns]))
        return q.count()

    def _page_directories(self, db: Session, *, storage_id: int, current_path: str, limit: int, cursor: Optional[dict]) -> dict:
        from sqlalchemy import not_
        from app.packages.system.models.directory_entry import DirectoryEntry
        from app.packages.system.crud.directory_entry import directory_entry_crud

        prefix = current_path
        q = (
            directory_entry_crud
            .query(db)
            .filter(DirectoryEntry.storage_id == storage_id)
            .filter(DirectoryEntry.path.like(prefix + "%"))
            .filter(not_(DirectoryEntry.path.like(prefix + "%/%")))
            .filter(not_(DirectoryEntry.path.like("/.thumbnails%")))
            .filter(not_(DirectoryEntry.path.like("/thumbnails%")))
        )
        # 游标：按路径名增序（不区分大小写）+ id
        from sqlalchemy import func, and_, or_
        sort_col = func.lower(DirectoryEntry.path)
        if cursor and cursor.get("part") == "dirs":
            last_key = cursor.get("k")
            last_id = int(cursor.get("id") or 0)
            q = q.filter(or_(sort_col > last_key, and_(sort_col == last_key, DirectoryEntry.id > last_id)))
        q = q.order_by(sort_col.asc(), DirectoryEntry.id.asc()).limit(limit + 1)
        rows = q.all()
        items: list[dict] = []
        next_cursor = None
        has_more = False
        if len(rows) > limit:
            has_more = True
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = base64_urlsafe_encode({"part": "dirs", "k": (last.path or "").lower(), "id": last.id})

        # 构造 name
        for d in rows:
            name = (d.path or "")[len(prefix) :].strip("/")
            if not name:
                continue
            items.append({"name": name, "type": "directory", "mimeType": None, "size": 0, "lastModified": None})
        return {"items": items, "nextCursor": next_cursor, "hasMore": has_more}

    def _page_files(
        self,
        db: Session,
        *,
        storage_id: int,
        dir_key: str,
        search: Optional[str],
        file_type: Optional[str],
        limit: int,
        cursor: Optional[dict],
        order_by: str,
        order_asc: bool,
        current_path: str,
    ) -> dict:
        from sqlalchemy import func, and_, or_
        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.file_record import file_record_crud

        q = (
            file_record_crud
            .query(db)
            .filter(FileRecord.storage_id == storage_id)
            .filter(FileRecord.directory == ("" if dir_key == "" else dir_key))
        )
        if search:
            s = f"%{search.lower()}%"
            q = q.filter(or_(func.lower(FileRecord.alias_name).like(s), func.lower(FileRecord.original_name).like(s)))
        if file_type and file_type != "all":
            exts = {
                "image": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp"},
                "document": {"doc", "docx", "odt"},
                "spreadsheet": {"xls", "xlsx", "ods"},
                "pdf": {"pdf"},
                "markdown": {"md"},
            }.get(file_type)
            if exts:
                patterns = tuple(f"%.{e}" for e in exts)
                q = q.filter(or_(*[FileRecord.alias_name.ilike(p) for p in patterns]))

        # 排序 + 游标
        if order_by == "size":
            sort_col = FileRecord.size_bytes
        elif order_by == "time":
            sort_col = FileRecord.update_time
        else:
            sort_col = func.lower(FileRecord.alias_name)

        if cursor and cursor.get("part") == "files" and cursor.get("ob") == order_by and cursor.get("od") == ("asc" if order_asc else "desc"):
            last_key = cursor.get("k")
            last_id = int(cursor.get("id") or 0)
            if order_asc:
                q = q.filter(or_(sort_col > last_key, and_(sort_col == last_key, FileRecord.id > last_id)))
            else:
                q = q.filter(or_(sort_col < last_key, and_(sort_col == last_key, FileRecord.id < last_id)))

        q = q.order_by((sort_col.asc() if order_asc else sort_col.desc()), (FileRecord.id.asc() if order_asc else FileRecord.id.desc())).limit(limit + 1)
        rows = q.all()

        items: list[dict] = []
        next_cursor = None
        has_more = False
        if len(rows) > limit:
            has_more = True
            last = rows[limit - 1]
            next_cursor = base64_urlsafe_encode({
                "part": "files",
                "ob": order_by,
                "od": "asc" if order_asc else "desc",
                "k": (getattr(last, "size_bytes", None) if order_by == "size" else (getattr(last, "update_time", None) if order_by == "time" else (last.alias_name or last.original_name or "")).lower()),
                "id": last.id,
            })
            rows = rows[:limit]

        for r in rows:
            name = r.alias_name or r.original_name
            file_item = {
                "name": name,
                "type": "file",
                "mimeType": r.mime_type,
                "size": int(r.size_bytes or 0),
                "lastModified": (getattr(r, "update_time", None) or getattr(r, "create_time", None)).isoformat() if getattr(r, "create_time", None) else None,
                "previewUrl": f"/api/v1/files/preview?storageId={storage_id}&path={current_path}{name}",
            }
            mime_lc = (r.mime_type or "").lower()
            if mime_lc.startswith("image/"):
                file_item["thumbnailUrl"] = f"/api/v1/files/thumbnail?storageId={storage_id}&path={current_path}{name}&w=256"
            items.append(file_item)

        return {"items": items, "nextCursor": next_cursor, "hasMore": has_more}


# 简单的 base64 urlsafe 编码/解码（避免重复导入）
def base64_urlsafe_encode(obj: dict) -> str:
    import base64, json
    return base64.urlsafe_b64encode(json.dumps(obj, default=str).encode("utf-8")).decode("ascii")

    # ----------------------------
    # 同步：对象存储/本地目录 -> 数据库 file_records
    # ----------------------------
    def sync_records(self, db: Session, *, storage_id: int, path: Optional[str] = "/") -> Dict[str, Any]:
        """扫描指定存储与路径下的文件，并将元数据同步到表 `file_records`。

        说明：
        - 写入“文件记录”和“目录记录”（目录以 directory_entries 存储）；
        - 文件若已存在（以 directory+alias_name 判定），则更新 size/mime；
        - 仅遍历单层目录并递归深入，S3 由于后端 list 限制为第一页，极大目录可能无法一次性完整同步；
        - 防御：跳过超长路径（>1024）条目；对异常做容错处理，尽力同步，不因单个目录/文件失败中断。
        """

        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.file_record import file_record_crud

        backend = self._get_backend(db, storage_id=storage_id)

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
        skipped = 0  # 记录因路径过长或异常而跳过的条目数

        visited: set[str] = set()

        def _walk(cur_path: str) -> None:
            nonlocal scanned, inserted, updated
            # 防止重复/环路
            safe_cur = cur_path if cur_path.endswith("/") else (cur_path + "/")
            if safe_cur in visited:
                return
            visited.add(safe_cur)

            try:
                data = backend.list(path=cur_path, file_type=None, search=None)
            except Exception:
                # 某些目录不可读/已被删除：跳过
                return
            cur_display = data.get("current_path") or (cur_path if cur_path.endswith("/") else (cur_path + "/"))
            _, dir_key = _norm_dir(cur_display)
            for it in data.get("items", []):
                if it.get("type") == "directory":
                    # 记录目录条目（不含末尾'/')，并下探
                    dir_path = f"{cur_display}{it['name']}"
                    if dir_path.endswith("/"):
                        dir_path = dir_path.rstrip("/")
                    # 跳过缩略图缓存目录
                    if it.get("name") in {".thumbnails", "thumbnails"}:
                        continue
                    # 路径长度防御
                    if len(dir_path) > 1024:
                        skipped += 1
                    else:
                        try:
                            from app.packages.system.crud.directory_entry import directory_entry_crud
                            from app.packages.system.models.directory_entry import DirectoryEntry
                            if dir_path and directory_entry_crud.get_by_path(db, storage_id=storage_id, path=dir_path) is None:
                                directory_entry_crud.create(db, {"storage_id": storage_id, "path": dir_path})
                        except Exception:
                            skipped += 1
                    _walk(f"{cur_display}{it['name']}")
                elif it.get("type") == "file":
                    scanned += 1
                    name = it.get("name")
                    size = int(it.get("size") or 0)
                    mime = it.get("mime_type")
                    # 查询是否存在
                    try:
                        # 过长路径/文件名防御
                        if len(f"{dir_key}/{name}") > 1024 or len(name or "") > 255:
                            skipped += 1
                            continue
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
                    except Exception:
                        skipped += 1

        # 开始遍历
        cur_display, _ = _norm_dir(path or "/")
        _walk(cur_display)

        return create_response(
            "同步完成",
            {"scanned": scanned, "inserted": inserted, "updated": updated, "skipped": skipped},
            HTTP_STATUS_OK,
        )

    # ----------------------------
    # 上传/下载/预览
    # ----------------------------
    async def upload(self, db: Session, *, storage_id: int, path: Optional[str], files: List[UploadFile], purpose: Optional[str] = None) -> List[dict]:
        backend = self._get_backend(db, storage_id=storage_id)
        materials: List[Tuple[str, bytes]] = []
        meta: List[Tuple[str, int, Optional[str]]] = []  # (orig_name, size, mime)
        for up in files:
            content = await up.read()
            orig_name = up.filename
            size = len(content)
            mime, _ = mimetypes.guess_type(orig_name or "")
            materials.append((orig_name, content))
            meta.append((orig_name, size, mime))
        results = backend.upload(path=path or "/", files=materials)

        # 将成功上传的文件写入数据库记录
        from app.packages.system.crud.file_record import file_record_crud

        norm_dir = (path or "/").strip()
        if not norm_dir.startswith("/"):
            norm_dir = "/" + norm_dir
        if not norm_dir.endswith("/"):
            norm_dir += "/"
        final_purpose = (purpose or "general").strip() or "general"

        for i, res in enumerate(results):
            try:
                if res.get("status") != "success":
                    continue
                orig_name = meta[i][0]
                size = meta[i][1]
                mime = meta[i][2]
                stored_name = res.get("stored_name") or orig_name
                file_record_crud.create(
                    db,
                    {
                        "storage_id": storage_id,
                        "directory": norm_dir.rstrip("/"),
                        "original_name": orig_name,
                        "alias_name": stored_name,
                        "purpose": final_purpose,
                        "size_bytes": size,
                        "mime_type": mime,
                    },
                )
            except Exception:
                # 记录失败不影响上传流程
                pass
        return results

    def download(self, db: Session, *, storage_id: int, path: str):
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.download(path=path)

    def preview(self, db: Session, *, storage_id: int, path: str):
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.preview(path=path)

    # ----------------------------
    # 目录与文件变更
    # ----------------------------
    def mkdir(self, db: Session, *, storage_id: int, parent: str, name: str) -> Dict[str, Any]:
        """创建文件夹，并将目录写入数据库 directory_entries。"""
        backend = self._get_backend(db, storage_id=storage_id)
        resp = backend.mkdir(parent=parent, name=name)

        # 将新建目录写入 DB，便于严格读库的列表立即感知
        try:
            folder_name: Optional[str] = None
            if isinstance(resp, dict):
                data = resp.get("data") or {}
                if isinstance(data, dict):
                    folder_name = data.get("folder_name")
            if folder_name:
                # 规范化父路径 -> 构造绝对目录路径（不以 '/' 结尾）
                par = (parent or "/").strip() or "/"
                if not par.startswith("/"):
                    par = "/" + par
                if not par.endswith("/"):
                    par = par + "/"
                full_path = (par + folder_name).rstrip("/")
                from app.packages.system.crud.directory_entry import directory_entry_crud
                from app.packages.system.models.directory_entry import DirectoryEntry

                # 若已存在则忽略；否则创建
                existing = (
                    directory_entry_crud
                    .query(db)
                    .filter(DirectoryEntry.storage_id == storage_id)
                    .filter(DirectoryEntry.path == full_path)
                    .first()
                )
                if existing is None:
                    directory_entry_crud.create(db, {"storage_id": storage_id, "path": full_path})
        except Exception:
            # DB 写入失败不影响主流程
            pass

        return resp

    def rename(self, db: Session, *, storage_id: int, old_path: str, new_path: str) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        resp = backend.rename(old_path=old_path, new_path=new_path)

        # 同步数据库：文件/目录重命名
        try:
            self._sync_rename_in_db(db, storage_id=storage_id, old_path=old_path, new_path=new_path)
        except Exception:
            pass
        return resp

    def move(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        resp = backend.move(source_paths=source_paths, destination_path=destination_path)
        try:
            self._sync_move_in_db(db, storage_id=storage_id, source_paths=source_paths, destination_path=destination_path)
        except Exception:
            pass
        return resp

    def copy(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        resp = backend.copy(source_paths=source_paths, destination_path=destination_path)
        try:
            self._sync_copy_in_db(db, storage_id=storage_id, source_paths=source_paths, destination_path=destination_path)
        except Exception:
            pass
        return resp

    def delete(self, db: Session, *, storage_id: int, paths: List[str]) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        resp = backend.delete(paths=paths)

        # 同步数据库：软删除对应的文件记录与目录记录
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.directory_entry import directory_entry_crud
        from app.packages.system.models.directory_entry import DirectoryEntry

        def _norm(p: str) -> str:
            s = (p or "/").strip()
            if not s.startswith("/"):
                s = "/" + s
            return s

        for raw in (paths or []):
            p = _norm(raw)
            # 尝试按“文件”删除：/a/b.txt -> dir=/a, name=b.txt
            parent = p.rsplit("/", 1)[0]
            name = p.rsplit("/", 1)[1] if "/" in p else p
            # 规范化父目录键（不以'/'结尾；根目录为 ""）
            dir_key = parent.rstrip("/")
            if dir_key == "/":
                dir_key = ""

            # 1) 文件记录：严格匹配 directory + alias_name
            try:
                q = (
                    file_record_crud
                    .query(db)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == dir_key)
                    .filter(FileRecord.alias_name == name)
                )
                for row in q.all():
                    file_record_crud.soft_delete(db, row)
            except Exception:
                pass

            # 2) 目录记录：若 raw 表示目录或存在同名目录，按前缀软删
            # 无法可靠判断传入是否目录，这里统一按目录前缀尝试一次（对单文件不会命中）
            try:
                # p_norm 用于目录匹配：不以'/'结尾
                p_norm = p.rstrip("/")
                if p_norm and p_norm != "/":
                    # directory_entries 路径前缀匹配
                    q_dirs = (
                        directory_entry_crud
                        .query(db)
                        .filter(DirectoryEntry.storage_id == storage_id)
                        .filter((DirectoryEntry.path == p_norm) | (DirectoryEntry.path.like(p_norm + "/%")))
                    )
                    for d in q_dirs.all():
                        directory_entry_crud.soft_delete(db, d)

                    # file_records 目录前缀匹配（当前目录及其子目录）
                    q_files = (
                        file_record_crud
                        .query(db)
                        .filter(FileRecord.storage_id == storage_id)
                        .filter((FileRecord.directory == p_norm) | (FileRecord.directory.like(p_norm + "/%")))
                    )
                    for fr in q_files.all():
                        file_record_crud.soft_delete(db, fr)
            except Exception:
                pass

        return resp

    # ----------------------------
    # 内部：DB 同步辅助
    # ----------------------------
    def _norm_abs_path(self, p: str) -> str:
        s = (p or "/").strip() or "/"
        if not s.startswith("/"):
            s = "/" + s
        # 保留传入的尾部斜杠语义到下游逻辑判断
        return s

    def _norm_dir_key(self, p: str) -> str:
        # 目录键：不以'/'结尾，根目录为空字符串
        s = self._norm_abs_path(p)
        s = s.rstrip("/")
        return "" if s == "/" else s

    def _ensure_dir_entry(self, db: Session, *, storage_id: int, dir_path: str) -> None:
        # dir_path: 绝对路径，不以'/'结尾
        from app.packages.system.crud.directory_entry import directory_entry_crud
        from app.packages.system.models.directory_entry import DirectoryEntry
        key = dir_path.rstrip("/")
        if key == "/":
            return
        existing = (
            directory_entry_crud
            .query(db)
            .filter(DirectoryEntry.storage_id == storage_id)
            .filter(DirectoryEntry.path == key)
            .first()
        )
        if existing is None:
            directory_entry_crud.create(db, {"storage_id": storage_id, "path": key})

    def _sync_rename_in_db(self, db: Session, *, storage_id: int, old_path: str, new_path: str) -> None:
        # 重命名 = 目录/文件从 old_path -> new_path
        old_abs = self._norm_abs_path(old_path)
        new_abs = self._norm_abs_path(new_path)
        # 目录情形：以'/'结尾或真实目录 -> 以前缀整体替换
        is_dir = old_abs.endswith("/") or new_abs.endswith("/")
        if is_dir:
            src_dir = old_abs.rstrip("/")
            dst_dir = new_abs.rstrip("/")
            self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_dir)
            self._replace_dir_prefix(db, storage_id, src_dir, dst_dir)
        else:
            # 文件重命名：更新单条记录的 directory/alias_name
            from app.packages.system.crud.file_record import file_record_crud
            from app.packages.system.models.file_record import FileRecord
            src_parent = old_abs.rsplit("/", 1)[0]
            src_name = old_abs.rsplit("/", 1)[1]
            dst_parent = new_abs.rsplit("/", 1)[0]
            dst_name = new_abs.rsplit("/", 1)[1]
            q = (
                file_record_crud
                .query(db)
                .filter(FileRecord.storage_id == storage_id)
                .filter(FileRecord.directory == self._norm_dir_key(src_parent))
                .filter(FileRecord.alias_name == src_name)
            )
            for row in q.all():
                row.directory = self._norm_dir_key(dst_parent)
                row.alias_name = dst_name
                file_record_crud.save(db, row)
            # 确保目标父目录存在于目录表
            self._ensure_dir_entry(db, storage_id=storage_id, dir_path=self._norm_dir_key(dst_parent) or "/")

    def _replace_dir_prefix(self, db: Session, storage_id: int, src_dir: str, dst_dir: str) -> None:
        # 将所有以 src_dir 为前缀的目录和文件目录替换为 dst_dir
        from app.packages.system.crud.directory_entry import directory_entry_crud
        from app.packages.system.models.directory_entry import DirectoryEntry
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.models.file_record import FileRecord

        prefix = src_dir
        if not prefix:
            return
        def _replace(path: str) -> str:
            if path == prefix:
                return dst_dir
            if path.startswith(prefix + "/"):
                return dst_dir + path[len(prefix):]
            return path

        # 目录表
        q_dirs = (
            directory_entry_crud
            .query(db)
            .filter(DirectoryEntry.storage_id == storage_id)
            .filter((DirectoryEntry.path == prefix) | (DirectoryEntry.path.like(prefix + "/%")))
        )
        for d in q_dirs.all():
            d.path = _replace(d.path)
            directory_entry_crud.save(db, d)
        # 文件表
        q_files = (
            file_record_crud
            .query(db)
            .filter(FileRecord.storage_id == storage_id)
            .filter((FileRecord.directory == prefix) | (FileRecord.directory.like(prefix + "/%")))
        )
        for f in q_files.all():
            f.directory = _replace(f.directory)
            file_record_crud.save(db, f)

    def _sync_move_in_db(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> None:
        dst_base = self._norm_abs_path(destination_path).rstrip("/")
        for spath in (source_paths or []):
            src_abs = self._norm_abs_path(spath)
            base_name = src_abs.rstrip("/").rsplit("/", 1)[-1]
            # 目录移动
            if src_abs.endswith("/"):
                src_dir = src_abs.rstrip("/")
                dst_dir = f"{dst_base}/{base_name}"
                self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_dir)
                self._replace_dir_prefix(db, storage_id, src_dir, dst_dir)
            else:
                # 文件移动：更新单条文件的 directory
                from app.packages.system.crud.file_record import file_record_crud
                from app.packages.system.models.file_record import FileRecord
                src_parent = src_abs.rsplit("/", 1)[0]
                name = src_abs.rsplit("/", 1)[1]
                dst_parent = dst_base
                self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_parent)
                q = (
                    file_record_crud
                    .query(db)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == self._norm_dir_key(src_parent))
                    .filter(FileRecord.alias_name == name)
                )
                for row in q.all():
                    row.directory = self._norm_dir_key(dst_parent)
                    file_record_crud.save(db, row)

    def _sync_copy_in_db(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> None:
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.crud.directory_entry import directory_entry_crud
        from app.packages.system.models.directory_entry import DirectoryEntry

        dst_base = self._norm_abs_path(destination_path).rstrip("/")
        for spath in (source_paths or []):
            src_abs = self._norm_abs_path(spath)
            base_name = src_abs.rstrip("/").rsplit("/", 1)[-1]
            if src_abs.endswith("/"):
                # 目录复制：复制目录表项和文件记录（前缀替换）
                src_dir = src_abs.rstrip("/")
                dst_dir = f"{dst_base}/{base_name}"
                self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_dir)

                # 复制目录表
                q_dirs = (
                    directory_entry_crud
                    .query(db)
                    .filter(DirectoryEntry.storage_id == storage_id)
                    .filter((DirectoryEntry.path == src_dir) | (DirectoryEntry.path.like(src_dir + "/%")))
                )
                for d in q_dirs.all():
                    suffix = d.path[len(src_dir):]
                    new_path = (dst_dir + suffix).rstrip("/")
                    if not (
                        directory_entry_crud
                        .query(db)
                        .filter(DirectoryEntry.storage_id == storage_id)
                        .filter(DirectoryEntry.path == new_path)
                        .first()
                    ):
                        directory_entry_crud.create(db, {"storage_id": storage_id, "path": new_path})

                # 复制文件表
                q_files = (
                    file_record_crud
                    .query(db)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter((FileRecord.directory == src_dir) | (FileRecord.directory.like(src_dir + "/%")))
                )
                for f in q_files.all():
                    suffix = f.directory[len(src_dir):]
                    new_dir = (dst_dir + suffix).rstrip("/")
                    # 创建副本记录
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
                        },
                    )
            else:
                # 文件复制：复制单条记录至目标目录
                src_parent = src_abs.rsplit("/", 1)[0]
                name = src_abs.rsplit("/", 1)[1]
                self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_base)
                row = (
                    file_record_crud
                    .query(db)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == self._norm_dir_key(src_parent))
                    .filter(FileRecord.alias_name == name)
                    .first()
                )
                if row is not None:
                    file_record_crud.create(
                        db,
                        {
                            "storage_id": storage_id,
                            "directory": self._norm_dir_key(dst_base),
                            "original_name": row.original_name,
                            "alias_name": row.alias_name,
                            "purpose": row.purpose,
                            "size_bytes": row.size_bytes,
                            "mime_type": row.mime_type,
                        },
                    )


file_service = FileService()
