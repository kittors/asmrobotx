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
from app.packages.system.core.logger import logger
from app.packages.system.utils.path_utils import (
    norm_abs_path as _norm_abs_path_util,
    norm_dir_key as _norm_dir_key_util,
)


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
            # 基于 fs_nodes 取“当前目录的直接子目录”
            from sqlalchemy import not_, or_, func
            from app.packages.system.models.fs_node import FsNode
            from app.packages.system.crud.fs_node import fs_node_crud

            prefix = (dir_key + "/") if dir_key else "/"
            q = (
                fs_node_crud
                .query(db)
                .filter(FsNode.storage_id == storage_id)
                .filter(FsNode.is_dir.is_(True))
                .filter(FsNode.path.like(prefix + "%"))
                .filter(not_(FsNode.path.like(prefix + "%/%")))
            )
            if search_lower:
                q = q.filter(func.lower(FsNode.name).like(f"%{search_lower}%"))
            for d in q.all():
                items.append({
                    "name": d.name,
                    "type": "directory",
                    "mimeType": None,
                    "size": 0,
                    "lastModified": getattr(d, "create_time", None).isoformat() if getattr(d, "create_time", None) else None,
                })

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
        raw_part = (include or "all").lower()
        # 默认/兼容：include 未指定或为 all 时，仅返回统一扁平视图 items（不再强制分区）
        part = "flat" if raw_part == "all" else raw_part
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

        # directories 分页（仅在显式 include=dirs 时返回）
        if part in ("dirs",):
            dirs_page = self._page_directories(
                db,
                storage_id=storage_id,
                current_path=current_path,
                limit=lmt,
                cursor=_decode_cursor(cursor),
                order_by=ob,
                order_asc=od_asc,
            )
            result["directories"] = dirs_page

        # files 分页（仅在显式 include=files 时返回）
        if part in ("files",):
            files_page = self._page_files(
                db,
                storage_id=storage_id,
                dir_key=dir_key,
                search=search,
                file_type=file_type,
                limit=lmt,
                cursor=_decode_cursor(cursor),
                order_by=ob,
                order_asc=od_asc,
                current_path=current_path,
            )
            result["files"] = files_page

        # 统一扁平 items 视图（默认返回）：从 fs_nodes 读取目录+文件，按 order_by/order 全局排序
        if part in ("flat",):
            result["items"] = self._page_flat_nodes(
                db,
                storage_id=storage_id,
                current_path=current_path,
                limit=lmt,
                cursor=_decode_cursor(cursor),
                order_by=ob,
                order_asc=od_asc,
                file_type=file_type,
                search=search,
                include_dirs=(False if (search and search.strip()) else True),
            )["items"]

        return create_response("获取文件列表成功", result, HTTP_STATUS_OK)

    def _count_directories(self, db: Session, *, storage_id: int, current_path: str) -> int:
        from sqlalchemy import not_
        from app.packages.system.models.fs_node import FsNode
        from app.packages.system.crud.fs_node import fs_node_crud
        prefix = current_path
        q = (
            fs_node_crud
            .query(db)
            .filter(FsNode.storage_id == storage_id)
            .filter(FsNode.is_dir.is_(True))
            .filter(FsNode.path.like(prefix + "%"))
            .filter(not_(FsNode.path.like(prefix + "%/%")))
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

    def _page_directories(self, db: Session, *, storage_id: int, current_path: str, limit: int, cursor: Optional[dict], order_by: str, order_asc: bool) -> dict:
        # 目录分页：支持 name/time 排序（time=按创建时间），Keyset 游标
        from sqlalchemy import func, and_, or_, not_
        from app.packages.system.models.fs_node import FsNode
        from app.packages.system.crud.fs_node import fs_node_crud

        prefix = current_path
        q = (
            fs_node_crud
            .query(db)
            .filter(FsNode.storage_id == storage_id)
            .filter(FsNode.is_dir.is_(True))
            .filter(FsNode.path.like(prefix + "%"))
            .filter(not_(FsNode.path.like(prefix + "%/%")))
        )
        # 排序列
        if order_by == "time":
            sort_col = FsNode.create_time  # 更符合“新建在前”的直觉
        else:
            # 默认按名称（不区分大小写）
            sort_col = func.lower(FsNode.path)

        # 游标（包含排序字段/方向以保证稳定翻页）
        if cursor and cursor.get("part") == "dirs" and cursor.get("ob") == order_by and cursor.get("od") == ("asc" if order_asc else "desc"):
            last_key = cursor.get("k")
            # time 排序需要把字符串解析回 datetime
            if order_by == "time" and isinstance(last_key, str):
                from datetime import datetime
                try:
                    last_key = datetime.fromisoformat(last_key)
                except Exception:
                    last_key = None
            last_id = int(cursor.get("id") or 0)
            if order_asc:
                q = q.filter(or_(sort_col > last_key, and_(sort_col == last_key, FsNode.id > last_id)))
            else:
                q = q.filter(or_(sort_col < last_key, and_(sort_col == last_key, FsNode.id < last_id)))

        q = q.order_by((sort_col.asc() if order_asc else sort_col.desc()), (FsNode.id.asc() if order_asc else FsNode.id.desc())).limit(limit + 1)
        rows = q.all()
        items: list[dict] = []
        next_cursor = None
        has_more = False
        if len(rows) > limit:
            has_more = True
            last = rows[limit - 1]
            next_cursor = base64_urlsafe_encode({
                "part": "dirs",
                "ob": order_by,
                "od": "asc" if order_asc else "desc",
                "k": (getattr(last, "create_time", None) if order_by == "time" else (last.path or "").lower()),
                "id": last.id,
            })
            rows = rows[:limit]

        # 构造 name
        for d in rows:
            name = d.name
            if not name:
                continue
            created_iso = getattr(d, "create_time", None).isoformat() if getattr(d, "create_time", None) else None
            items.append({
                "name": name,
                "type": "directory",
                "mimeType": None,
                "size": 0,
                "lastModified": created_iso,
                "createdAt": created_iso,
            })
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
            # 改为按创建时间排序，满足“新文件在前”的需求
            sort_col = FileRecord.create_time
        else:
            sort_col = func.lower(FileRecord.alias_name)

        if cursor and cursor.get("part") == "files" and cursor.get("ob") == order_by and cursor.get("od") == ("asc" if order_asc else "desc"):
            last_key = cursor.get("k")
            if order_by == "time" and isinstance(last_key, str):
                # 将 ISO 字符串恢复为 datetime
                from datetime import datetime
                try:
                    last_key = datetime.fromisoformat(last_key)
                except Exception:
                    last_key = None
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
                "k": (getattr(last, "size_bytes", None) if order_by == "size" else (getattr(last, "create_time", None) if order_by == "time" else (last.alias_name or last.original_name or "")).lower()),
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
                # lastModified 维持“显示更新/创建时间”的语义，兼容既有前端
                "lastModified": (
                    (getattr(r, "update_time", None) or getattr(r, "create_time", None)).isoformat()
                    if getattr(r, "create_time", None)
                    else None
                ),
                # 补充 createdAt/updatedAt 以支持服务端聚合排序与前端按需展示
                "createdAt": getattr(r, "create_time", None).isoformat() if getattr(r, "create_time", None) else None,
                "updatedAt": getattr(r, "update_time", None).isoformat() if getattr(r, "update_time", None) else None,
                "previewUrl": f"/api/v1/files/preview?storageId={storage_id}&path={current_path}{name}",
            }
            mime_lc = (r.mime_type or "").lower()
            if mime_lc.startswith("image/"):
                file_item["thumbnailUrl"] = f"/api/v1/files/thumbnail?storageId={storage_id}&path={current_path}{name}&w=256"
            items.append(file_item)

        return {"items": items, "nextCursor": next_cursor, "hasMore": has_more}

    def _page_flat_nodes(
        self,
        db: Session,
        *,
        storage_id: int,
        current_path: str,
        limit: int,
        cursor: Optional[dict],
        order_by: str,
        order_asc: bool,
        file_type: Optional[str],
        search: Optional[str],
        include_dirs: bool = True,
    ) -> dict:
        from sqlalchemy import func, and_, or_, not_
        from app.packages.system.models.fs_node import FsNode
        from app.packages.system.crud.fs_node import fs_node_crud

        prefix = current_path  # current_path 形如 '/docs/' 或 '/'
        q = (
            fs_node_crud
            .query(db)
            .filter(FsNode.storage_id == storage_id)
            .filter(FsNode.path.like(prefix + "%"))
            .filter(not_(FsNode.path.like(prefix + "%/%")))
        )
        # 搜索
        if search:
            s = f"%{search.lower()}%"
            q = q.filter(or_(func.lower(FsNode.name).like(s), func.lower(FsNode.path).like(s)))
            # 在关键词搜索场景下，默认仅返回文件，避免“搜文件名”时混入目录
            if not include_dirs:
                q = q.filter(FsNode.is_dir.is_(False))
        # 文件类型过滤（仅对文件生效）
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
                q = q.filter(or_(FsNode.is_dir == True, or_(*[FsNode.name.ilike(p) for p in patterns])))

        # 排序列
        if order_by == "size":
            sort_col = FsNode.size_bytes
        elif order_by == "time":
            sort_col = FsNode.create_time
        else:
            sort_col = func.lower(FsNode.name)

        # 游标
        if cursor and cursor.get("part") == "flat" and cursor.get("ob") == order_by and cursor.get("od") == ("asc" if order_asc else "desc"):
            last_key = cursor.get("k")
            if order_by == "time" and isinstance(last_key, str):
                from datetime import datetime
                try:
                    last_key = datetime.fromisoformat(last_key)
                except Exception:
                    last_key = None
            last_id = int(cursor.get("id") or 0)
            if order_asc:
                q = q.filter(or_(sort_col > last_key, and_(sort_col == last_key, FsNode.id > last_id)))
            else:
                q = q.filter(or_(sort_col < last_key, and_(sort_col == last_key, FsNode.id < last_id)))

        q = q.order_by((sort_col.asc() if order_asc else sort_col.desc()), (FsNode.id.asc() if order_asc else FsNode.id.desc())).limit(limit + 1)
        rows = q.all()
        items: list[dict] = []
        next_cursor = None
        has_more = False
        if len(rows) > limit:
            has_more = True
            last = rows[limit - 1]
            next_cursor = base64_urlsafe_encode({
                "part": "flat",
                "ob": order_by,
                "od": "asc" if order_asc else "desc",
                "k": (getattr(last, "create_time", None) if order_by == "time" else (last.name or "").lower() if order_by == "name" else int(last.size_bytes or 0)),
                "id": last.id,
            })
            rows = rows[:limit]

        # 组装输出
        for n in rows:
            if n.is_dir:
                items.append({
                    "name": n.name,
                    "type": "directory",
                    "mimeType": None,
                    "size": 0,
                    "lastModified": getattr(n, "create_time", None).isoformat() if getattr(n, "create_time", None) else None,
                    "createdAt": getattr(n, "create_time", None).isoformat() if getattr(n, "create_time", None) else None,
                })
            else:
                item = {
                    "name": n.name,
                    "type": "file",
                    "mimeType": n.mime_type,
                    "size": int(n.size_bytes or 0),
                    "lastModified": getattr(n, "update_time", None).isoformat() if getattr(n, "update_time", None) else (getattr(n, "create_time", None).isoformat() if getattr(n, "create_time", None) else None),
                    "createdAt": getattr(n, "create_time", None).isoformat() if getattr(n, "create_time", None) else None,
                    "previewUrl": f"/api/v1/files/preview?storageId={storage_id}&path={current_path}{n.name}",
                }
                mime_lc = (n.mime_type or "").lower()
                if mime_lc.startswith("image/"):
                    item["thumbnailUrl"] = f"/api/v1/files/thumbnail?storageId={storage_id}&path={current_path}{n.name}&w=256"
                items.append(item)

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
        - 写入“文件记录”和“统一节点”（目录/文件按 fs_nodes 存储）；
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
                            from app.packages.system.crud.fs_node import fs_node_crud
                            if dir_path and fs_node_crud.get_by_path(db, storage_id=storage_id, path=dir_path) is None:
                                base_name = dir_path.rsplit("/", 1)[-1]
                                fs_node_crud.create(db, {"storage_id": storage_id, "path": dir_path, "name": base_name, "is_dir": True})
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
        """创建文件夹，并将目录写入统一表 fs_nodes。"""
        backend = self._get_backend(db, storage_id=storage_id)
        resp = backend.mkdir(parent=parent, name=name)

        # 将新建目录写入 DB（fs_nodes），便于严格读库的列表立即感知
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
                from app.packages.system.crud.fs_node import fs_node_crud
                # 若已存在则忽略；否则创建
                node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=full_path)
                if node is None:
                    fs_node_crud.create(db, {"storage_id": storage_id, "path": full_path, "name": folder_name, "is_dir": True})
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
        # 调用仅-DB 同步，避免二次调用存储后端
        try:
            self._sync_delete_in_db(db, storage_id=storage_id, paths=paths)
        except Exception:
            pass
        return resp

    def _sync_delete_in_db(self, db: Session, *, storage_id: int, paths: List[str]) -> dict:
        """仅同步数据库的删除（配合已完成的存储删除）。

        返回删除统计，便于上层在响应中透出，帮助前端/排障确认 DB 已更新。
        """
        # 同步数据库：软删除对应的文件记录与统一节点
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.models.file_record import FileRecord
        from app.packages.system.models.fs_node import FsNode
        from app.packages.system.crud.fs_node import fs_node_crud

        try:
            logger.info("sync_delete.start storage_id=%s paths_in=%s", storage_id, paths)
        except Exception:
            pass
        files_deleted = 0
        nodes_deleted = 0

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

            # 1) 文件记录：严格匹配 directory + alias_name（物理删除）
            try:
                # 直接使用底层 Query，避免数据域导致的遗漏
                q = (
                    db.query(FileRecord)
                    .filter(FileRecord.storage_id == storage_id)
                    .filter(FileRecord.directory == dir_key)
                    .filter(FileRecord.alias_name == name)
                )
                for row in q.all():
                    try:
                        file_record_crud.hard_delete(db, row)
                        files_deleted += 1
                    except Exception:
                        file_record_crud.soft_delete(db, row)
                        files_deleted += 1
            except Exception:
                pass
            # 统一表：单文件节点物理删除
            try:
                node = db.query(FsNode).filter(FsNode.storage_id == storage_id, FsNode.path == p.rstrip("/")).first()
                if node is not None:
                    try:
                        fs_node_crud.hard_delete(db, node)
                        nodes_deleted += 1
                    except Exception:
                        fs_node_crud.soft_delete(db, node)
                        nodes_deleted += 1
            except Exception:
                pass

            # 2) 目录记录：若 raw 表示目录或存在同名目录，按前缀软删（仅 file_records 与 fs_nodes）
            # 无法可靠判断传入是否目录，这里统一按目录前缀尝试一次（对单文件不会命中）
            try:
                # p_norm 用于目录匹配：不以'/'结尾
                p_norm = p.rstrip("/")
                if p_norm and p_norm != "/":
                    # file_records 目录前缀匹配（当前目录及其子目录）
                    q_files = (
                        db.query(FileRecord)
                        .filter(FileRecord.storage_id == storage_id)
                        .filter((FileRecord.directory == p_norm) | (FileRecord.directory.like(p_norm + "/%")))
                    )
                    for fr in q_files.all():
                        try:
                            file_record_crud.hard_delete(db, fr)
                            files_deleted += 1
                        except Exception:
                            file_record_crud.soft_delete(db, fr)
                            files_deleted += 1
                    # 统一表：目录前缀软删
                    try:
                        qn = (
                            db.query(FsNode)
                            .filter(FsNode.storage_id == storage_id)
                            .filter((FsNode.path == p_norm) | (FsNode.path.like(p_norm + "/%")))
                        )
                        for n in qn.all():
                            try:
                                fs_node_crud.hard_delete(db, n)
                                nodes_deleted += 1
                            except Exception:
                                fs_node_crud.soft_delete(db, n)
                                nodes_deleted += 1
                    except Exception:
                        pass
            except Exception:
                pass

        result = {"filesDeleted": files_deleted, "nodesDeleted": nodes_deleted}
        try:
            logger.info("sync_delete.done storage_id=%s result=%s", storage_id, result)
        except Exception:
            pass
        return result

    # ----------------------------
    # 内部：DB 同步辅助
    # ----------------------------
    def _norm_abs_path(self, p: str) -> str:
        """Normalize to absolute path starting with '/', no trailing '/'."""
        return _norm_abs_path_util(p)

    def _norm_dir_key(self, p: str) -> str:
        """Normalize directory key: absolute path without trailing '/' (root -> '')."""
        return _norm_dir_key_util(p)

    def _ensure_dir_entry(self, db: Session, *, storage_id: int, dir_path: str) -> None:
        # dir_path: 绝对路径，不以'/'结尾；在 fs_nodes 中确保存在目录节点
        from app.packages.system.crud.fs_node import fs_node_crud
        key = dir_path.rstrip("/")
        if key == "/":
            return
        node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=key)
        if node is None:
            base_name = key.rsplit("/", 1)[-1]
            fs_node_crud.create(db, {"storage_id": storage_id, "path": key, "name": base_name, "is_dir": True})

    def _sync_rename_in_db(self, db: Session, *, storage_id: int, old_path: str, new_path: str) -> None:
        # 重命名 = 目录/文件从 old_path -> new_path
        old_abs = self._norm_abs_path(old_path)
        new_abs = self._norm_abs_path(new_path)
        # 目录情形判断：优先依据 fs_nodes 再回退尾斜杠语义
        is_dir = False
        try:
            from app.packages.system.crud.fs_node import fs_node_crud
            node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=old_abs.rstrip("/"))
            is_dir = bool(node and getattr(node, "is_dir", False))
        except Exception:
            is_dir = False
        if not is_dir:
            is_dir = old_abs.endswith("/") or new_abs.endswith("/")
        if is_dir:
            src_dir = old_abs.rstrip("/")
            dst_dir = new_abs.rstrip("/")
            self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_dir)
            self._replace_dir_prefix(db, storage_id, src_dir, dst_dir)
            # 统一表：批量前缀替换
            try:
                from app.packages.system.crud.fs_node import fs_node_crud
                from app.packages.system.models.fs_node import FsNode
                q = (
                    fs_node_crud
                    .query(db)
                    .filter(FsNode.storage_id == storage_id)
                    .filter((FsNode.path == src_dir) | (FsNode.path.like(src_dir + "/%")))
                )
                for n in q.all():
                    if n.path == src_dir:
                        n.path = dst_dir
                        n.name = dst_dir.rsplit("/", 1)[-1]
                    elif n.path.startswith(src_dir + "/"):
                        n.path = dst_dir + n.path[len(src_dir):]
                        n.name = n.path.rsplit("/", 1)[-1]
                    fs_node_crud.save(db, n)
            except Exception:
                pass
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
            matched = False
            for row in q.all():
                row.directory = self._norm_dir_key(dst_parent)
                row.alias_name = dst_name
                file_record_crud.save(db, row)
                matched = True
            # 若未匹配到文件记录，回退：从目标父目录读取元信息并补写记录，避免必须手动“同步”。
            if not matched:
                try:
                    backend = self._get_backend(db, storage_id=storage_id)
                    meta = None
                    try:
                        listing = backend.list(path=dst_parent)
                        for it in listing.get("items", []) or []:
                            if it.get("type") == "file" and (it.get("name") or "") == dst_name:
                                meta = it
                                break
                    except Exception:
                        meta = None
                    file_record_crud.create(
                        db,
                        {
                            "storage_id": storage_id,
                            "directory": self._norm_dir_key(dst_parent),
                            "original_name": dst_name,
                            "alias_name": dst_name,
                            "purpose": "general",
                            "size_bytes": int((meta or {}).get("size") or 0),
                            "mime_type": (meta or {}).get("mime_type"),
                        },
                    )
                except Exception:
                    pass
            # 确保目标父目录存在于目录表
            self._ensure_dir_entry(db, storage_id=storage_id, dir_path=self._norm_dir_key(dst_parent) or "/")
            # 统一表：单条文件重命名
            try:
                from app.packages.system.crud.fs_node import fs_node_crud
                from app.packages.system.models.fs_node import FsNode
                src_full = old_abs.rstrip("/")
                dst_full = new_abs.rstrip("/")
                node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=src_full)
                if node is not None:
                    node.path = dst_full
                    node.name = dst_name
                    fs_node_crud.save(db, node)
                else:
                    # 源节点不在 DB，则 upsert 目标节点
                    if fs_node_crud.get_by_path(db, storage_id=storage_id, path=dst_full) is None:
                        fs_node_crud.create(db, {
                            "storage_id": storage_id,
                            "path": dst_full,
                            "name": dst_name,
                            "is_dir": False,
                        })
            except Exception:
                pass

    def _replace_dir_prefix(self, db: Session, storage_id: int, src_dir: str, dst_dir: str) -> None:
        # 将所有以 src_dir 为前缀的“目录节点”和“文件记录目录”替换为 dst_dir
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
        # 统一表：批量替换（目录与文件节点）
        try:
            from app.packages.system.crud.fs_node import fs_node_crud
            from app.packages.system.models.fs_node import FsNode
            q_nodes = (
                fs_node_crud
                .query(db)
                .filter(FsNode.storage_id == storage_id)
                .filter((FsNode.path == src_dir) | (FsNode.path.like(src_dir + "/%")))
            )
            for n in q_nodes.all():
                if n.path == src_dir:
                    n.path = dst_dir
                elif n.path.startswith(src_dir + "/"):
                    n.path = dst_dir + n.path[len(src_dir):]
                n.name = n.path.rsplit("/", 1)[-1]
                fs_node_crud.save(db, n)
        except Exception:
            pass

    def _sync_move_in_db(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> None:
        dst_base = self._norm_abs_path(destination_path).rstrip("/")
        for spath in (source_paths or []):
            src_abs = self._norm_abs_path(spath)
            base_name = src_abs.rstrip("/").rsplit("/", 1)[-1]
            # 判断是否目录：优先依据 fs_nodes，再回退尾斜杠
            is_dir = False
            try:
                from app.packages.system.crud.fs_node import fs_node_crud
                node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=src_abs.rstrip("/"))
                is_dir = bool(node and getattr(node, "is_dir", False))
            except Exception:
                is_dir = False
            if not is_dir and src_abs.endswith("/"):
                is_dir = True
            # 目录移动
            if is_dir:
                src_dir = src_abs.rstrip("/")
                dst_dir = f"{dst_base}/{base_name}"
                self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_dir)
                self._replace_dir_prefix(db, storage_id, src_dir, dst_dir)
                # 统一表的批量替换已在 _replace_dir_prefix 中完成
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
                matched = False
                for row in q.all():
                    row.directory = self._norm_dir_key(dst_parent)
                    file_record_crud.save(db, row)
                    matched = True
                # 统一表：移动单文件
                try:
                    from app.packages.system.crud.fs_node import fs_node_crud
                    src_full = src_abs.rstrip("/")
                    dst_full = f"{dst_base}/{name}"
                    node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=src_full)
                    if node is not None:
                        node.path = dst_full
                        node.name = name
                        fs_node_crud.save(db, node)
                except Exception:
                    pass

                # 回退路径：若未匹配到任何文件记录（例如源文件尚未入库），
                # 直接基于存储后端读取目标文件元信息并补写一条记录，避免必须手动“同步”。
                if not matched:
                    try:
                        backend = self._get_backend(db, storage_id=storage_id)
                        # 在目标父目录下查找该文件
                        meta = None
                        try:
                            listing = backend.list(path=dst_parent)
                            for it in listing.get("items", []):
                                if it.get("type") == "file" and (it.get("name") or "") == name:
                                    meta = it
                                    break
                        except Exception:
                            meta = None
                        file_record_crud.create(
                            db,
                            {
                                "storage_id": storage_id,
                                "directory": self._norm_dir_key(dst_parent),
                                "original_name": name,
                                "alias_name": name,
                                "purpose": "general",
                                "size_bytes": int((meta or {}).get("size") or 0),
                                "mime_type": (meta or {}).get("mime_type"),
                            },
                        )
                        # 统一表：补写文件节点
                        try:
                            from app.packages.system.crud.fs_node import fs_node_crud
                            full_path = f"{dst_parent}/{name}".rstrip("/")
                            if fs_node_crud.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                                fs_node_crud.create(db, {
                                    "storage_id": storage_id,
                                    "path": full_path,
                                    "name": name,
                                    "is_dir": False,
                                    "size_bytes": int((meta or {}).get("size") or 0),
                                    "mime_type": (meta or {}).get("mime_type"),
                                })
                        except Exception:
                            pass
                    except Exception:
                        # 外层兜底，任何异常不影响主流程
                        pass

    def _sync_copy_in_db(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> None:
        """在完成后端物理复制后，尽力将目标侧的 DB 元数据补齐。

        目标：避免用户必须再点一次“同步”才能看到刚复制的内容。
        策略：
        - 若源条目已在 DB：直接按既有元数据写入目标侧（更快）。
        - 若源条目不在 DB：从目标父目录列一遍，取到 size/mime 后写入；
        - 复制“目录”时，为稳妥起见对目标子树执行一次微同步（LOCAL/S3 通用）。
        """
        from app.packages.system.crud.file_record import file_record_crud
        from app.packages.system.models.file_record import FileRecord

        backend = self._get_backend(db, storage_id=storage_id)
        dst_base = self._norm_abs_path(destination_path).rstrip("/")

        for spath in (source_paths or []):
            src_abs = self._norm_abs_path(spath)
            base_name = src_abs.rstrip("/").rsplit("/", 1)[-1]

            # 判定目录/文件
            is_dir = False
            try:
                from app.packages.system.crud.fs_node import fs_node_crud
                node = fs_node_crud.get_by_path(db, storage_id=storage_id, path=src_abs.rstrip("/"))
                is_dir = bool(node and getattr(node, "is_dir", False))
            except Exception:
                is_dir = False
            if not is_dir and src_abs.endswith("/"):
                is_dir = True

            if is_dir:
                # 目录：确保目录节点，然后对目标目录做一次小范围同步，最稳
                dst_dir = f"{dst_base}/{base_name}"
                self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_dir)
                try:
                    from app.packages.system.services.sync_service import sync_records
                    sync_records(db, storage_id=storage_id, path=dst_dir + "/")
                except Exception:
                    pass
                continue

            # 文件：优先引用源文件记录；否则从目标父目录读取元信息
            src_parent = src_abs.rsplit("/", 1)[0]
            name = base_name
            self._ensure_dir_entry(db, storage_id=storage_id, dir_path=dst_base)

            row = (
                file_record_crud
                .query(db)
                .filter(FileRecord.storage_id == storage_id)
                .filter(FileRecord.directory == self._norm_dir_key(src_parent))
                .filter(FileRecord.alias_name == name)
                .first()
            )

            size_v: int = 0
            mime_v: Optional[str] = None
            if row is None:
                # 目标父目录列一遍，抓取该文件的 size/mime
                try:
                    listing = backend.list(path=dst_base)
                    for it in listing.get("items", []) or []:
                        if (it.get("type") == "file") and ((it.get("name") or "") == name):
                            size_v = int(it.get("size") or 0)
                            mime_v = it.get("mime_type")
                            break
                except Exception:
                    size_v = 0
                    mime_v = None

                file_record_crud.create(
                    db,
                    {
                        "storage_id": storage_id,
                        "directory": self._norm_dir_key(dst_base),
                        "original_name": name,
                        "alias_name": name,
                        "purpose": "general",
                        "size_bytes": size_v,
                        "mime_type": mime_v,
                    },
                )
            else:
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

            # 统一表：文件节点 upsert（若无则创建）
            try:
                from app.packages.system.crud.fs_node import fs_node_crud
                full_path = f"{dst_base}/{name}".rstrip("/")
                if fs_node_crud.get_by_path(db, storage_id=storage_id, path=full_path) is None:
                    fs_node_crud.create(db, {
                        "storage_id": storage_id,
                        "path": full_path,
                        "name": name,
                        "is_dir": False,
                        "size_bytes": int((row.size_bytes if row is not None else size_v) or 0),
                        "mime_type": (row.mime_type if row is not None else mime_v),
                    })
            except Exception:
                pass
file_service = FileService()
