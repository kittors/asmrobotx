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
    ) -> Dict[str, Any]:
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
            items.append(
                {
                    "name": name,
                    "type": "file",
                    "mimeType": r.mime_type,
                    "size": int(r.size_bytes or 0),
                    "lastModified": (getattr(r, "update_time", None) or getattr(r, "create_time", None)).isoformat() if getattr(r, "create_time", None) else None,
                    "previewUrl": f"/api/v1/files/preview?storageId={storage_id}&path={current_path}{name}",
                }
            )

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
    # 同步：对象存储/本地目录 -> 数据库 file_records
    # ----------------------------
    def sync_records(self, db: Session, *, storage_id: int, path: Optional[str] = "/") -> Dict[str, Any]:
        """扫描指定存储与路径下的文件，并将元数据同步到表 `file_records`。

        说明：
        - 写入“文件记录”和“目录记录”（目录以 directory_entries 存储）；
        - 文件若已存在（以 directory+alias_name 判定），则更新 size/mime；
        - 仅遍历单层目录并递归深入，S3 由于后端 list 限制为第一页，极大目录可能无法一次性完整同步。
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

        def _walk(cur_path: str) -> None:
            nonlocal scanned, inserted, updated
            data = backend.list(path=cur_path, file_type=None, search=None)
            cur_display = data.get("current_path") or (cur_path if cur_path.endswith("/") else (cur_path + "/"))
            _, dir_key = _norm_dir(cur_display)
            for it in data.get("items", []):
                if it.get("type") == "directory":
                    # 记录目录条目（不含末尾'/')
                    try:
                        from app.packages.system.crud.directory_entry import directory_entry_crud
                        from app.packages.system.models.directory_entry import DirectoryEntry
                        dir_path = f"{cur_display}{it['name']}"
                        if dir_path.endswith("/"):
                            dir_path = dir_path.rstrip("/")
                        if dir_path and directory_entry_crud.get_by_path(db, storage_id=storage_id, path=dir_path) is None:
                            directory_entry_crud.create(
                                db,
                                {
                                    "storage_id": storage_id,
                                    "path": dir_path,
                                },
                            )
                    except Exception:
                        # 目录表写入失败不影响继续扫描
                        pass
                    _walk(f"{cur_display}{it['name']}")
                elif it.get("type") == "file":
                    scanned += 1
                    name = it.get("name")
                    size = int(it.get("size") or 0)
                    mime = it.get("mime_type")
                    # 查询是否存在
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

        # 开始遍历
        cur_display, _ = _norm_dir(path or "/")
        _walk(cur_display)

        return create_response(
            "同步完成",
            {"scanned": scanned, "inserted": inserted, "updated": updated},
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
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.mkdir(parent=parent, name=name)

    def rename(self, db: Session, *, storage_id: int, old_path: str, new_path: str) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.rename(old_path=old_path, new_path=new_path)

    def move(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.move(source_paths=source_paths, destination_path=destination_path)

    def copy(self, db: Session, *, storage_id: int, source_paths: List[str], destination_path: str) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.copy(source_paths=source_paths, destination_path=destination_path)

    def delete(self, db: Session, *, storage_id: int, paths: List[str]) -> Dict[str, Any]:
        backend = self._get_backend(db, storage_id=storage_id)
        return backend.delete(paths=paths)


file_service = FileService()
