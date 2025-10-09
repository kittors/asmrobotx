"""存储后端抽象与实现：统一封装本地与 S3 的文件操作。"""

from __future__ import annotations

import io
import mimetypes
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from app.packages.system.core.exceptions import AppException
from app.packages.system.core.logger import logger
from app.packages.system.core.responses import create_response
from fastapi import status
from app.packages.system.core.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)


def _norm_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


# ------------------------------------------
# 公共数据结构
# ------------------------------------------

@dataclass
class ListItem:
    name: str
    type: str  # "file" | "directory"
    mime_type: Optional[str]
    size: int
    last_modified: Optional[str]


class StorageBackend:
    """存储后端接口。"""

    def list(
        self,
        *,
        path: str,
        file_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        raise NotImplementedError

    def upload(self, *, path: str, files: List[Tuple[str, bytes]]) -> list[dict]:
        raise NotImplementedError

    def download(self, *, path: str):  # StreamingResponse | RedirectResponse
        raise NotImplementedError

    def preview(self, *, path: str):  # StreamingResponse | RedirectResponse
        return self.download(path=path)

    def mkdir(self, *, parent: str, name: str) -> dict:
        raise NotImplementedError

    def rename(self, *, old_path: str, new_path: str) -> dict:
        raise NotImplementedError

    def move(self, *, source_paths: List[str], destination_path: str) -> dict:
        raise NotImplementedError

    def copy(self, *, source_paths: List[str], destination_path: str) -> dict:
        raise NotImplementedError

    def delete(self, *, paths: List[str]) -> dict:
        raise NotImplementedError


# ------------------------------------------
# 本地文件系统实现
# ------------------------------------------


class LocalBackend(StorageBackend):
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        if not self.root.exists():
            try:
                self.root.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # pragma: no cover - 极端情况下可能失败
                raise AppException(f"无法创建本地根目录: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

    # 统一的安全路径拼接，防止路径遍历
    def _resolve(self, rel: str) -> Path:
        rel_norm = rel.strip()
        if rel_norm.startswith("/"):
            rel_norm = rel_norm[1:]
        candidate = (self.root / rel_norm).resolve()
        try:
            candidate.relative_to(self.root)
        except Exception as exc:
            raise AppException("非法路径: 越权访问", HTTP_STATUS_BAD_REQUEST) from exc
        return candidate

    def _filter_type(self, name: str, file_type: Optional[str]) -> bool:
        if not file_type or file_type == "all":
            return True
        ext = Path(name).suffix.lower().lstrip(".")
        groups = {
            "image": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp"},
            "document": {"doc", "docx", "odt"},
            "spreadsheet": {"xls", "xlsx", "ods"},
            "pdf": {"pdf"},
            "markdown": {"md"},
        }
        allowed = groups.get(file_type)
        if allowed is None:
            return True
        return ext in allowed

    def list(self, *, path: str, file_type: Optional[str] = None, search: Optional[str] = None) -> dict:
        base = self._resolve(path or "")
        if not base.exists():
            raise AppException("路径不存在", HTTP_STATUS_NOT_FOUND)
        if not base.is_dir():
            raise AppException("目标不是文件夹", HTTP_STATUS_BAD_REQUEST)

        items: list[dict] = []
        search_lower = (search or "").strip().lower()
        try:
            for entry in sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                name = entry.name
                if search_lower and search_lower not in name.lower():
                    continue
                if entry.is_dir():
                    items.append(
                        {
                            "name": name,
                            "type": "directory",
                            "mime_type": None,
                            "size": 0,
                            "last_modified": datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).isoformat(),
                        }
                    )
                else:
                    if not self._filter_type(name, file_type):
                        continue
                    abs_path = str(entry)
                    items.append(
                        {
                            "name": name,
                            "type": "file",
                            "mime_type": _norm_mime(abs_path),
                            "size": int(entry.stat().st_size),
                            "last_modified": datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).isoformat(),
                        }
                    )
        except PermissionError as exc:
            raise AppException("无法读取目录内容：权限不足", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

        current_path = "/" + (str(base.relative_to(self.root)) if base != self.root else "")
        if not current_path.endswith("/"):
            current_path += "/"
        return {"current_path": current_path, "items": items}

    def upload(self, *, path: str, files: List[Tuple[str, bytes]]) -> list[dict]:
        target_dir = self._resolve(path or "")
        if not target_dir.exists() or not target_dir.is_dir():
            raise AppException("上传目标目录不存在", HTTP_STATUS_NOT_FOUND)

        results: list[dict] = []
        for filename, content in files:
            safe_name = os.path.basename(filename)
            dst = target_dir / safe_name
            if dst.exists():
                results.append({"name": safe_name, "status": "failure", "message": "上传失败：文件名已存在"})
                continue
            try:
                with open(dst, "wb") as f:
                    f.write(content)
                results.append({"name": safe_name, "status": "success", "message": "文件上传成功"})
            except Exception as exc:
                logger.exception("Local upload failed: %s", exc)
                results.append({"name": safe_name, "status": "failure", "message": "上传失败：服务器错误"})
        return results

    def download(self, *, path: str):
        target = self._resolve(path)
        if not target.exists() or not target.is_file():
            raise AppException("文件不存在", HTTP_STATUS_NOT_FOUND)
        return FileResponse(
            str(target),
            media_type=_norm_mime(str(target)),
            filename=target.name,
        )

    def preview(self, *, path: str):  # inline
        target = self._resolve(path)
        if not target.exists() or not target.is_file():
            raise AppException("文件不存在", HTTP_STATUS_NOT_FOUND)
        f = open(target, "rb")
        return StreamingResponse(f, media_type=_norm_mime(str(target)))

    def mkdir(self, *, parent: str, name: str) -> dict:
        parent_dir = self._resolve(parent)
        if not parent_dir.exists() or not parent_dir.is_dir():
            raise AppException("父目录不存在", HTTP_STATUS_NOT_FOUND)
        safe_name = os.path.basename(name.strip())
        if not safe_name:
            raise AppException("文件夹名称不能为空", HTTP_STATUS_BAD_REQUEST)
        new_dir = parent_dir / safe_name
        if new_dir.exists():
            raise AppException("同名文件或文件夹已存在", HTTP_STATUS_BAD_REQUEST)
        new_dir.mkdir(parents=False, exist_ok=False)
        return create_response("文件夹创建成功", {"folder_name": safe_name}, HTTP_STATUS_OK)

    def rename(self, *, old_path: str, new_path: str) -> dict:
        src = self._resolve(old_path)
        dst = self._resolve(new_path)
        if not src.exists():
            raise AppException("源路径不存在", HTTP_STATUS_NOT_FOUND)
        if dst.exists():
            raise AppException("目标路径已存在", HTTP_STATUS_BAD_REQUEST)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return create_response("重命名成功", None, HTTP_STATUS_OK)

    def move(self, *, source_paths: List[str], destination_path: str) -> dict:
        dst_dir = self._resolve(destination_path)
        if not dst_dir.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)
        if not dst_dir.is_dir():
            raise AppException("目标路径必须为文件夹", HTTP_STATUS_BAD_REQUEST)

        for spath in source_paths:
            src = self._resolve(spath)
            if not src.exists():
                raise AppException(f"源路径不存在: {spath}", HTTP_STATUS_NOT_FOUND)
            dst = dst_dir / src.name
            if dst.exists():
                raise AppException(f"目标已存在: {dst.name}", HTTP_STATUS_BAD_REQUEST)
            shutil.move(str(src), str(dst))
        return create_response("文件/文件夹移动成功", None, HTTP_STATUS_OK)

    def copy(self, *, source_paths: List[str], destination_path: str) -> dict:
        dst_dir = self._resolve(destination_path)
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not dst_dir.is_dir():
            raise AppException("目标路径必须为文件夹", HTTP_STATUS_BAD_REQUEST)

        for spath in source_paths:
            src = self._resolve(spath)
            if not src.exists():
                raise AppException(f"源路径不存在: {spath}", HTTP_STATUS_NOT_FOUND)
            dst = dst_dir / src.name
            if dst.exists():
                raise AppException(f"目标已存在: {dst.name}", HTTP_STATUS_BAD_REQUEST)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        return create_response("文件/文件夹复制成功", None, HTTP_STATUS_OK)

    def delete(self, *, paths: List[str]) -> dict:
        for rel in paths:
            target = self._resolve(rel)
            if not target.exists():
                # 允许幂等：不存在则忽略
                continue
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        return create_response("文件/文件夹删除成功", None, HTTP_STATUS_OK)


# ------------------------------------------
# S3 实现（boto3）
# ------------------------------------------


class S3Backend(StorageBackend):
    def __init__(self, *, bucket: str, region: str, access_key_id: str, secret_access_key: str, prefix: Optional[str] = None):
        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise AppException(
                "S3 功能不可用：缺少依赖 boto3，请在后端安装后重试",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        self.boto3 = boto3
        self.bucket = bucket
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.prefix = (prefix or "").lstrip("/")
        self._client = self.boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    # 拼接基于 path_prefix 的对象 key
    def _join_key(self, rel: str) -> str:
        rel_norm = rel.lstrip("/")
        if self.prefix:
            if rel_norm:
                return f"{self.prefix.rstrip('/')}/{rel_norm}"
            return self.prefix.rstrip("/") + "/"
        return rel_norm

    def _is_allowed_type(self, name: str, file_type: Optional[str]) -> bool:
        if not file_type or file_type == "all":
            return True
        ext = Path(name).suffix.lower().lstrip(".")
        groups = {
            "image": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp"},
            "document": {"doc", "docx", "odt"},
            "spreadsheet": {"xls", "xlsx", "ods"},
            "pdf": {"pdf"},
            "markdown": {"md"},
        }
        allowed = groups.get(file_type)
        if allowed is None:
            return True
        return ext in allowed

    def list(self, *, path: str, file_type: Optional[str] = None, search: Optional[str] = None) -> dict:
        prefix = self._join_key(path)
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        paginator = self._client.get_paginator("list_objects_v2")
        page_iter = paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/")

        items: list[dict] = []
        search_lower = (search or "").strip().lower()

        for page in page_iter:
            for common in page.get("CommonPrefixes", []):  # folders
                key = common.get("Prefix", "")
                name = key[len(prefix) :].rstrip("/") if prefix else key.rstrip("/")
                if not name:
                    continue
                if search_lower and search_lower not in name.lower():
                    continue
                items.append(
                    {
                        "name": name,
                        "type": "directory",
                        "mime_type": None,
                        "size": 0,
                        "last_modified": None,
                    }
                )
            for content in page.get("Contents", []):  # files at this level
                key = content.get("Key")
                if not key or key.endswith("/"):
                    continue
                name = key[len(prefix) :] if prefix else key
                if "/" in name:  # deeper file, skip because Delimiter='/'
                    continue
                if search_lower and search_lower not in name.lower():
                    continue
                if not self._is_allowed_type(name, file_type):
                    continue
                items.append(
                    {
                        "name": name,
                        "type": "file",
                        "mime_type": _norm_mime(name),
                        "size": int(content.get("Size") or 0),
                        "last_modified": content.get("LastModified").astimezone(timezone.utc).isoformat() if content.get("LastModified") else None,
                    }
                )

        current_path = path if path else "/"
        if not current_path.endswith("/"):
            current_path += "/"
        return {"current_path": current_path, "items": items}

    def upload(self, *, path: str, files: List[Tuple[str, bytes]]) -> list[dict]:
        results: list[dict] = []
        base_prefix = self._join_key(path)
        if base_prefix and not base_prefix.endswith("/"):
            base_prefix += "/"
        for filename, content in files:
            key = base_prefix + os.path.basename(filename)
            # 冲突检测：查询是否存在同名对象
            exists = False
            try:
                resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=key, MaxKeys=1)
                exists = (resp.get("KeyCount") or 0) > 0 and resp.get("Contents", [{}])[0].get("Key") == key
            except Exception:
                exists = False
            if exists:
                results.append({"name": os.path.basename(filename), "status": "failure", "message": "上传失败：文件名已存在"})
                continue
            try:
                self._client.upload_fileobj(io.BytesIO(content), self.bucket, key)
                results.append({"name": os.path.basename(filename), "status": "success", "message": "文件上传成功"})
            except Exception as exc:
                logger.exception("S3 upload failed: %s", exc)
                results.append({"name": os.path.basename(filename), "status": "failure", "message": "上传失败：服务器错误"})
        return results

    def _presign(self, *, key: str, download: bool = True, filename: Optional[str] = None) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if download and filename:
            params["ResponseContentDisposition"] = f"attachment; filename=\"{filename}\""
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=300,
            )
            return url
        except Exception as exc:
            raise AppException(f"预签名 URL 生成失败: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

    def download(self, *, path: str):
        key = self._join_key(path)
        filename = os.path.basename(path)
        url = self._presign(key=key, download=True, filename=filename)
        return RedirectResponse(url)

    def preview(self, *, path: str):
        key = self._join_key(path)
        url = self._presign(key=key, download=False)
        return RedirectResponse(url)

    def mkdir(self, *, parent: str, name: str) -> dict:
        base = self._join_key(parent)
        if base and not base.endswith("/"):
            base += "/"
        folder_key = f"{base}{name.strip().strip('/')}".strip("/") + "/"
        # 创建一个占位对象
        self._client.put_object(Bucket=self.bucket, Key=folder_key)
        return create_response("文件夹创建成功", {"folder_name": name}, HTTP_STATUS_OK)

    def rename(self, *, old_path: str, new_path: str) -> dict:
        src_key = self._join_key(old_path)
        dst_key = self._join_key(new_path)
        # 目录重命名：批量复制
        if src_key.endswith("/") or new_path.endswith("/"):
            return self._move_copy_prefix(src_key if src_key.endswith("/") else src_key + "/", dst_key if dst_key.endswith("/") else dst_key + "/", delete_source=True)
        # 文件重命名
        self._client.copy_object(Bucket=self.bucket, Key=dst_key, CopySource={"Bucket": self.bucket, "Key": src_key})
        self._client.delete_object(Bucket=self.bucket, Key=src_key)
        return create_response("重命名成功", None, HTTP_STATUS_OK)

    def move(self, *, source_paths: List[str], destination_path: str) -> dict:
        dst_prefix = self._join_key(destination_path)
        if dst_prefix and not dst_prefix.endswith("/"):
            dst_prefix += "/"
        for spath in source_paths:
            src_key = self._join_key(spath)
            base_name = os.path.basename(spath.strip("/"))
            if src_key.endswith("/"):
                self._move_copy_prefix(src_key, dst_prefix + base_name + "/", delete_source=True)
            else:
                self._client.copy_object(
                    Bucket=self.bucket,
                    Key=dst_prefix + base_name,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                )
                self._client.delete_object(Bucket=self.bucket, Key=src_key)
        return create_response("文件/文件夹移动成功", None, HTTP_STATUS_OK)

    def copy(self, *, source_paths: List[str], destination_path: str) -> dict:
        dst_prefix = self._join_key(destination_path)
        if dst_prefix and not dst_prefix.endswith("/"):
            dst_prefix += "/"
        for spath in source_paths:
            src_key = self._join_key(spath)
            base_name = os.path.basename(spath.strip("/"))
            if src_key.endswith("/"):
                self._move_copy_prefix(src_key, dst_prefix + base_name + "/", delete_source=False)
            else:
                self._client.copy_object(
                    Bucket=self.bucket,
                    Key=dst_prefix + base_name,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                )
        return create_response("文件/文件夹复制成功", None, HTTP_STATUS_OK)

    def delete(self, *, paths: List[str]) -> dict:
        objects_to_delete: list[dict] = []
        for rel in paths:
            key = self._join_key(rel)
            if key.endswith("/"):
                # 列举所有对象
                paginator = self._client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket, Prefix=key):
                    for obj in page.get("Contents", []):
                        objects_to_delete.append({"Key": obj["Key"]})
            else:
                objects_to_delete.append({"Key": key})
        # 批量删除（分批防止一次过多）
        for i in range(0, len(objects_to_delete), 1000):
            batch = objects_to_delete[i : i + 1000]
            if batch:
                self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})
        return create_response("文件/文件夹删除成功", None, HTTP_STATUS_OK)

    # 批量复制（可选删除源）
    def _move_copy_prefix(self, src_prefix: str, dst_prefix: str, *, delete_source: bool) -> dict:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=src_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                suffix = key[len(src_prefix) :]
                new_key = dst_prefix + suffix
                self._client.copy_object(Bucket=self.bucket, Key=new_key, CopySource={"Bucket": self.bucket, "Key": key})
        if delete_source:
            self.delete(paths=[src_prefix])
        return create_response("操作成功", None, HTTP_STATUS_OK)


def build_backend(
    *,
    type: str,
    region: Optional[str] = None,
    bucket_name: Optional[str] = None,
    path_prefix: Optional[str] = None,
    local_root_path: Optional[str] = None,
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
) -> StorageBackend:
    t = (type or "").upper()
    if t == "LOCAL":
        if not local_root_path:
            raise AppException("缺少本地根目录配置", HTTP_STATUS_BAD_REQUEST)
        return LocalBackend(local_root_path)
    if t == "S3":
        if not (region and bucket_name and access_key_id and secret_access_key):
            raise AppException("S3 配置不完整", HTTP_STATUS_BAD_REQUEST)
        return S3Backend(
            bucket=bucket_name,
            region=region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            prefix=path_prefix,
        )
    raise AppException("不支持的存储类型", HTTP_STATUS_BAD_REQUEST)
