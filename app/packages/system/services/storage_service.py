"""存储源配置服务：提供 CRUD 与连接测试能力。"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.packages.system.core.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_CONFLICT,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from app.packages.system.core.exceptions import AppException
from app.packages.system.core.responses import create_response
from app.packages.system.core.timezone import format_datetime
from app.packages.system.crud.storage_config import storage_config_crud
from app.packages.system.models.storage import StorageConfig
from app.packages.system.services.storage_backends import build_backend


class StorageService:
    # ----------------------------
    # 列表与详情
    # ----------------------------
    def list_configs(self, db: Session) -> Dict[str, Any]:
        items = storage_config_crud.list_all(db)
        data = [self._serialize_config(item, include_status=True) for item in items]
        return create_response("获取存储源配置成功", data, HTTP_STATUS_OK)

    def create_config(self, db: Session, payload: dict) -> Dict[str, Any]:
        normalized = self._normalize_payload(payload, partial=False)
        existing = storage_config_crud.get_by_name(db, normalized["name"], include_deleted=True)
        if existing is not None:
            raise AppException("存储源名称已存在", HTTP_STATUS_CONFLICT)

        created = storage_config_crud.create(db, normalized)
        # 可选：立即测试连接并返回状态
        data = self._serialize_config(created, include_status=True)
        return create_response("创建存储源成功", data, HTTP_STATUS_OK)

    def update_config(self, db: Session, *, id: int, payload: dict) -> Dict[str, Any]:
        config = storage_config_crud.get(db, id)
        if config is None:
            raise AppException("存储源不存在或已删除", HTTP_STATUS_NOT_FOUND)

        merged = self._normalize_payload(payload, partial=True, existing=config)
        # 名称唯一性校验
        if "name" in merged and merged["name"] != config.name:
            if storage_config_crud.get_by_name(db, merged["name"], include_deleted=True):
                raise AppException("存储源名称已存在", HTTP_STATUS_CONFLICT)

        for k, v in merged.items():
            setattr(config, k, v)
        saved = storage_config_crud.save(db, config)
        return create_response("更新存储源成功", self._serialize_config(saved, include_status=True), HTTP_STATUS_OK)

    def delete_config(self, db: Session, *, id: int) -> Dict[str, Any]:
        config = storage_config_crud.get(db, id)
        if config is None:
            raise AppException("存储源不存在或已删除", HTTP_STATUS_NOT_FOUND)
        storage_config_crud.soft_delete(db, config)
        return create_response("删除存储源成功", None, HTTP_STATUS_OK)

    def test_connection(self, db: Session, payload: dict) -> Dict[str, Any]:
        normalized = self._normalize_payload(payload, partial=False)
        # 仅做连通性测试，不保存
        try:
            backend = build_backend(
                type=normalized["type"],
                region=normalized.get("region"),
                bucket_name=normalized.get("bucket_name"),
                path_prefix=normalized.get("path_prefix"),
                local_root_path=normalized.get("local_root_path"),
                access_key_id=normalized.get("access_key_id"),
                secret_access_key=normalized.get("secret_access_key"),
            )
            # 做一次最轻量的探测
            if normalized["type"].upper() == "LOCAL":
                # 目录可达即可
                _ = backend.list(path="/")
            else:
                # S3 尝试列目录
                _ = backend.list(path="/")
        except AppException as exc:
            return create_response("连接失败：" + str(exc), {"success": False}, HTTP_STATUS_OK)
        except Exception as exc:
            return create_response("连接失败：" + str(exc), {"success": False}, HTTP_STATUS_OK)
        return create_response("连接测试成功", {"success": True}, HTTP_STATUS_OK)

    # ----------------------------
    # 工具方法
    # ----------------------------
    def _normalize_payload(self, payload: dict, *, partial: bool, existing: Optional[StorageConfig] = None) -> dict:
        def _opt(x: Optional[str]) -> Optional[str]:
            if x is None:
                return None
            t = x.strip()
            return t or None

        t = (payload.get("type") or (existing.type if existing else "")).strip().upper()
        if not t:
            raise AppException("存储类型不能为空", HTTP_STATUS_BAD_REQUEST)
        if t not in {"S3", "LOCAL"}:
            raise AppException("存储类型仅支持 S3 或 LOCAL", HTTP_STATUS_BAD_REQUEST)

        result: dict = {}
        if not partial or "name" in payload:
            name = (payload.get("name") or (existing.name if existing else "")).strip()
            if not name:
                raise AppException("存储源名称不能为空", HTTP_STATUS_BAD_REQUEST)
            result["name"] = name

        result["type"] = t

        if t == "S3":
            for key in ("region", "bucket_name", "access_key_id", "secret_access_key", "path_prefix"):
                if not partial or key in payload:
                    result[key] = _opt(payload.get(key))
            # 必填校验
            for req in ("region", "bucket_name", "access_key_id", "secret_access_key"):
                if not result.get(req):
                    raise AppException(f"S3 配置字段 {req} 不能为空", HTTP_STATUS_BAD_REQUEST)
        else:  # LOCAL
            if not partial or "local_root_path" in payload:
                root = _opt(payload.get("local_root_path"))
                if not root and not partial:
                    raise AppException("本地根目录不能为空", HTTP_STATUS_BAD_REQUEST)
                if root:
                    # 归一化绝对路径
                    result["local_root_path"] = os.path.abspath(root)

        return result

    def _serialize_config(self, item: StorageConfig, *, include_status: bool = False) -> dict[str, Any]:
        data = {
            "id": item.id,
            "name": item.name,
            "type": item.type,
            "region": item.region,
            "bucket_name": item.bucket_name,
            "path_prefix": item.path_prefix,
            "local_root_path": item.local_root_path,
            "created_at": format_datetime(item.create_time),
        }
        if include_status:
            try:
                backend = build_backend(
                    type=item.type,
                    region=item.region,
                    bucket_name=item.bucket_name,
                    path_prefix=item.path_prefix,
                    local_root_path=item.local_root_path,
                    access_key_id=item.access_key_id,
                    secret_access_key=item.secret_access_key,
                )
                # 简单探测
                if item.type.upper() == "LOCAL":
                    _ = backend.list(path="/")
                else:
                    _ = backend.list(path="/")
                data["status"] = "connected"
            except Exception:
                data["status"] = "error"
        return data


storage_service = StorageService()

