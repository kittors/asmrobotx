"""缩略图服务：懒生成 + 存储级缓存（兼容本地与 S3）。

- 接口：get_or_create(db, storage_id, path, width, height, fmt, quality)
  - 首次生成，之后复用；
  - 本地：文件放在 <root>/.thumbnails/<dir>/<name>__w{w}[x{h}].{fmt}
  - S3：对象放在 thumbnails/<dir>/<name>__w{w}[x{h}].{fmt}
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional, Tuple

from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
import sys
import platform
import traceback

from app.packages.system.core.exceptions import AppException
from app.packages.system.core.constants import HTTP_STATUS_BAD_REQUEST, HTTP_STATUS_NOT_FOUND
from sqlalchemy.orm import Session

from app.packages.system.crud.storage_config import storage_config_crud
from app.packages.system.services.storage_backends import build_backend, LocalBackend, S3Backend


def _is_image_name(name: str) -> bool:
    ext = Path(name or "").suffix.lower()
    return ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}


class ThumbnailService:
    DEFAULT_WIDTH = 256
    DEFAULT_FMT = "webp"  # webp/jpeg/png
    DEFAULT_QUALITY = 75
    MAX_ORIG_BYTES = 20 * 1024 * 1024  # 20MB 安全上限

    def get_or_create(
        self,
        db: Session,
        *,
        storage_id: int,
        path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fmt: Optional[str] = None,
        quality: Optional[int] = None,
    ):
        width = int(width or self.DEFAULT_WIDTH)
        if height is not None:
            height = int(height)
        fmt_req = (fmt or self.DEFAULT_FMT).lower()
        quality = int(quality or self.DEFAULT_QUALITY)

        # 规范化原始路径
        rel = (path or "").strip()
        if not rel:
            raise AppException("参数 path 不能为空", HTTP_STATUS_BAD_REQUEST)
        if not rel.startswith("/"):
            rel = "/" + rel
        # 基础校验
        if not _is_image_name(rel):
            raise AppException("仅支持图片生成缩略图", HTTP_STATUS_BAD_REQUEST)

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

        # 根据运行环境能力决定最终输出格式（例如 Pillow 未启用 webp 时退回 jpg）
        eff_fmt = self._effective_format(fmt_req)

        # 目标缩略图相对存储路径（基于最终输出格式计算文件名）
        thumb_dir, thumb_name = self._thumb_relpath(rel, width, height, eff_fmt, backend)

        # 命中缓存：直接返回
        if isinstance(backend, LocalBackend):
            abs_thumb = Path(cfg.local_root_path).resolve() / thumb_dir.lstrip("/") / thumb_name
            if abs_thumb.exists():
                return FileResponse(str(abs_thumb), media_type=self._mime_for(fmt), filename=thumb_name)
        else:  # S3
            try:
                s3: S3Backend = backend  # type: ignore
                key = s3._join_key(f"{thumb_dir}{thumb_name}")
                s3._client.head_object(Bucket=s3.bucket, Key=key)
                # 缓存命中：复用 S3Backend 预览（直链或预签名）
                return backend.preview(path=f"{thumb_dir}{thumb_name}")
            except Exception:
                pass

        # 缓存未命中：生成（不再自动回退原图，直接暴露真实错误，便于定位根因）
        image_bytes = self._load_original_bytes(cfg, backend, rel)
        thumb_bytes = self._make_thumbnail(image_bytes, width=width, height=height, fmt=eff_fmt, quality=quality)

        # 写入存储
        if isinstance(backend, LocalBackend):
            root = Path(cfg.local_root_path).resolve()
            dst_dir = (root / thumb_dir.lstrip("/")).resolve()
            dst_dir.mkdir(parents=True, exist_ok=True)
            abs_thumb = dst_dir / thumb_name
            with open(abs_thumb, "wb") as f:
                f.write(thumb_bytes)
            return FileResponse(str(abs_thumb), media_type=self._mime_for(eff_fmt), filename=thumb_name)
        else:
            # 上传到 thumbnails 目录
            backend.upload(path=thumb_dir, files=[(thumb_name, thumb_bytes)])
            return backend.preview(path=f"{thumb_dir}{thumb_name}")

    # --------------------- helpers ---------------------
    def _thumb_relpath(self, rel: str, w: int, h: Optional[int], fmt: str, backend) -> Tuple[str, str]:
        # rel: "/dir/a.jpg" -> dir="/dir", name="a", ext
        parent = "/" + rel.strip("/").rsplit("/", 1)[0] if "/" in rel.strip("/") else "/"
        base = rel.strip("/").rsplit("/", 1)[-1]
        stem = Path(base).stem
        suffix = f"__w{w}{'x'+str(h) if h else ''}.{fmt}"
        name = stem + suffix
        if isinstance(backend, LocalBackend):
            # 本地：/.thumbnails/<parent-without-trailing-slash>/
            dir_rel = parent.rstrip("/")
            return f"/.thumbnails{dir_rel if dir_rel else ''}/", name
        else:
            # S3：thumbnails/<parent-without-leading-slash>/
            dir_rel = rel.strip("/").rsplit("/", 1)[0] if "/" in rel.strip("/") else ""
            return f"/thumbnails/{dir_rel}/" if dir_rel else "/thumbnails/", name

    def _load_original_bytes(self, cfg, backend, rel: str) -> bytes:
        if isinstance(backend, LocalBackend):
            abs_path = Path(cfg.local_root_path).resolve() / rel.lstrip("/")
            if not abs_path.exists() or not abs_path.is_file():
                raise AppException("原始图片不存在", HTTP_STATUS_NOT_FOUND)
            if abs_path.stat().st_size > self.MAX_ORIG_BYTES:
                raise AppException("原始图片过大，无法生成缩略图", HTTP_STATUS_BAD_REQUEST)
            with open(abs_path, "rb") as f:
                return f.read()
        else:
            s3: S3Backend = backend  # type: ignore
            key = s3._join_key(rel)
            # 过大限制（用 HeadObject 先看长度）
            try:
                head = s3._client.head_object(Bucket=s3.bucket, Key=key)
                size = int(head.get("ContentLength") or 0)
                if size > self.MAX_ORIG_BYTES:
                    raise AppException("原始图片过大，无法生成缩略图", HTTP_STATUS_BAD_REQUEST)
            except AppException:
                raise
            except Exception:
                pass
            obj = s3._client.get_object(Bucket=s3.bucket, Key=key)
            return obj["Body"].read()

    def _make_thumbnail(self, data: bytes, *, width: int, height: Optional[int], fmt: str, quality: int) -> bytes:
        try:
            from PIL import Image, features
        except ImportError as exc:
            # 这里提供精确的环境信息，帮助用户定位“为什么导入失败”
            details = (
                f"Pillow 导入失败: {exc};\n"
                f"python={sys.version};\n"
                f"exe={sys.executable}; platform={platform.platform()}; machine={platform.machine()}\n"
                f"sys.path[0:3]={sys.path[:3]}"
            )
            # 延伸：把完整堆栈写入日志（不暴露给客户端）
            try:
                from app.packages.system.core.logger import logger  # 延迟导入避免循环
                logger.error("Thumbnail import error: %s\n%s", details, traceback.format_exc())
            except Exception:
                pass
            raise AppException(
                "缩略图依赖加载失败：当前运行环境无法导入 Pillow。"
                "请确认服务使用的 Python 解释器与安装 Pillow 的环境一致（例如通过 .venv/bin/uvicorn 启动），"
                "或重新安装 Pillow 以匹配当前平台/架构。",
                HTTP_STATUS_BAD_REQUEST,
            ) from exc

        # 安全解码，部分格式需要转换
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img

        # 等比缩放到指定边界（cover/fit：这里采用最长边等比不超过 w/h）
        target = (width, height or width)
        img.thumbnail(target, Image.LANCZOS)

        # 输出
        out = io.BytesIO()
        fmt_lc = fmt.lower()
        # 如果请求 webp 但运行环境未启用 webp，则回退到 JPEG
        if fmt_lc == "webp" and hasattr(features, "check") and not features.check("webp"):
            fmt_lc = "jpeg"
        try:
            if fmt_lc == "png":
                img.save(out, format="PNG", optimize=True)
            elif fmt_lc in ("jpg", "jpeg"):
                img.save(out, format="JPEG", quality=quality, optimize=True)
            else:  # webp
                img.save(out, format="WEBP", quality=quality, method=6)
        except Exception:
            # 最终兜底：若指定格式保存失败，尝试以 PNG 输出
            out = io.BytesIO()
            img.save(out, format="PNG", optimize=True)
        return out.getvalue()

    def _mime_for(self, fmt: str) -> str:
        m = fmt.lower()
        if m == "png":
            return "image/png"
        if m in ("jpg", "jpeg"):
            return "image/jpeg"
        return "image/webp"

    def _effective_format(self, requested: str) -> str:
        """根据运行时特性决定最终输出格式。

        - 如请求 webp 而 Pillow 未启用 webp 编码，则回退到 jpeg；
        - 其它格式按请求返回。
        """
        req = (requested or self.DEFAULT_FMT).lower()
        if req != "webp":
            return req
        try:
            from PIL import features  # type: ignore
            if hasattr(features, "check") and features.check("webp"):
                return "webp"
            return "jpeg"
        except Exception:
            # 无法检测能力时保守回退为 jpeg
            return "jpeg"


thumbnail_service = ThumbnailService()
