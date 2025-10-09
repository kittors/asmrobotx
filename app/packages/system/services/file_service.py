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
        backend = self._get_backend(db, storage_id=storage_id)
        data = backend.list(path=path or "/", file_type=file_type, search=search)
        # 追加 previewUrl 便于前端点击预览
        items = []
        for item in data.get("items", []):
            # 字段名转换为前端文档的 camelCase
            converted = {
                "name": item.get("name"),
                "type": item.get("type"),
                "mimeType": item.get("mime_type"),
                "size": item.get("size"),
                "lastModified": item.get("last_modified"),
            }
            if item.get("type") == "file":
                preview_url = f"/api/v1/files/preview?storageId={storage_id}&path={(data['current_path'] or '/')}{item['name']}"
                converted["previewUrl"] = preview_url
            items.append(converted)
        current_path = data.get("current_path", "/")
        root_path: Optional[str] = None
        # 若为本地存储，额外返回根目录的绝对路径（currentPath 仍保持相对路径样式）
        try:
            from app.packages.system.crud.storage_config import storage_config_crud

            cfg = storage_config_crud.get(db, storage_id)
            if cfg and (cfg.type or "").upper() == "LOCAL" and cfg.local_root_path:
                root_path = os.path.abspath(cfg.local_root_path)
        except Exception:
            pass

        payload = {
            "currentPath": current_path,
            "items": items,
        }
        if root_path:
            payload["rootPath"] = root_path
        return create_response("获取文件列表成功", payload, HTTP_STATUS_OK)

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
