"""文件操作服务：基于存储源配置执行各类文件/文件夹操作。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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
        payload = {
            "currentPath": data.get("current_path", "/"),
            "items": items,
        }
        return create_response("获取文件列表成功", payload, HTTP_STATUS_OK)

    # ----------------------------
    # 上传/下载/预览
    # ----------------------------
    async def upload(self, db: Session, *, storage_id: int, path: Optional[str], files: List[UploadFile]) -> List[dict]:
        backend = self._get_backend(db, storage_id=storage_id)
        materials: List[Tuple[str, bytes]] = []
        for up in files:
            content = await up.read()
            materials.append((up.filename, content))
        results = backend.upload(path=path or "/", files=materials)
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
