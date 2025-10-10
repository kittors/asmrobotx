"""文件与文件夹操作路由。

为与操作日志监听规则对齐，补充对变更类接口的操作日志记录（上传/重命名/移动/复制/删除/新建/粘贴/剪贴板写入与清空）。
查询类接口（列表/下载/预览/剪贴板获取）保持轻量，不记录以避免日志噪音。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.files import (
    DeleteBody,
    FilesListResponse,
    FilesMutationResponse,
    ClipboardSetBody,
    ClipboardGetResponse,
    FolderCreateBody,
    MoveCopyBody,
    RenameBody,
)
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.logger import logger
from app.packages.system.core.timezone import now as tz_now
from app.packages.system.core.responses import create_response
from app.packages.system.core.constants import HTTP_STATUS_OK
from app.packages.system.models.user import User
from app.packages.system.services.file_service import file_service
from app.packages.system.services.clipboard_service import clipboard_service
from app.packages.system.services.log_service import log_service
from app.packages.system.services.thumbnail_service import thumbnail_service

router = APIRouter(tags=["files"])


@router.get("/files", response_model=FilesListResponse)
def list_items(
    storage_id: int = Query(..., alias="storageId"),
    path: Optional[str] = Query("/"),
    file_type: Optional[str] = Query(None, alias="fileType"),
    search: Optional[str] = Query(None),
    # 分页/排序（向后兼容：不传这些参数则返回旧结构）
    limit: Optional[int] = Query(None, ge=1, le=500),
    cursor: Optional[str] = Query(None),
    include: Optional[str] = Query(None, pattern=r"^(dirs|files|all)$"),
    order_by: Optional[str] = Query(None, alias="orderBy", pattern=r"^(name|size|time)$"),
    order: Optional[str] = Query(None, pattern=r"^(asc|desc)$"),
    count_only: bool = Query(False, alias="countOnly"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.list_items(
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


@router.post("/files/sync", response_model=FilesMutationResponse)
def sync_db_from_storage(
    request: Request,
    storage_id: int = Query(..., alias="storageId"),
    path: Optional[str] = Query("/"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """从对象存储/本地目录扫描并同步文件元数据到数据库。

    仅影响数据库记录，不会改动实际存储；可配合前端“同步”按钮使用。
    """
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        # 在少量运行环境中可能遇到实例方法属性不可见的问题，这里显式通过类方法调用以增强鲁棒性。
        try:
            from app.packages.system.services.file_service import FileService as _FS
            resp = _FS.sync_records(file_service, db, storage_id=storage_id, path=path)
        except Exception:
            # 回退到实例方法（若可用）
            resp = file_service.sync_records(db, storage_id=storage_id, path=path)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="other",
            class_method="app.packages.system.api.v1.endpoints.files.sync_db_from_storage",
            request_body={"storage_id": storage_id, "path": path},
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/files", response_model=FilesMutationResponse)
async def upload_files(
    request: Request,
    storage_id: int = Query(..., alias="storageId"),
    path: Optional[str] = Query("/"),
    purpose: Optional[str] = Query(None, description="上传目的，可选，默认 general"),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        # 直接使用存储后端上传，随后写入 file_records
        backend = file_service._get_backend(db, storage_id=storage_id)
        materials: list[tuple[str, bytes]] = []
        meta: list[tuple[str, int, Optional[str]]] = []
        import mimetypes
        for up in files:
            content = await up.read()
            orig_name = up.filename
            size = len(content)
            mime, _ = mimetypes.guess_type(orig_name or "")
            materials.append((orig_name, content))
            meta.append((orig_name, size, mime))
        results = backend.upload(path=path or "/", files=materials)

        # 记录到数据库（失败不影响上传）
        try:
            from app.packages.system.crud.file_record import file_record_crud
            norm_dir = (path or "/").strip()
            if not norm_dir.startswith("/"):
                norm_dir = "/" + norm_dir
            if norm_dir.endswith("/"):
                norm_dir = norm_dir.rstrip("/")
            final_purpose = (purpose or "general").strip() or "general"
            for i, res in enumerate(results):
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
                        "directory": norm_dir,
                        "original_name": orig_name,
                        "alias_name": stored_name,
                        "purpose": final_purpose,
                        "size_bytes": size,
                        "mime_type": mime,
                    },
                )
        except Exception:
            pass

        resp = create_response("上传完成", results, HTTP_STATUS_OK)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="create",
            class_method="app.packages.system.api.v1.endpoints.files.upload_files",
            request_body={
                "storage_id": storage_id,
                "path": path,
                "purpose": purpose,
                "filenames": [f.filename for f in (files or [])],
            },
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/files/download")
def download_file(
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    backend = file_service._get_backend(db, storage_id=storage_id)
    return backend.download(path=path)


@router.get("/files/preview")
def preview_file(
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    backend = file_service._get_backend(db, storage_id=storage_id)
    return backend.preview(path=path)


@router.get("/files/thumbnail")
def get_thumbnail(
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(..., description="原始图片相对路径，形如 /dir/a.jpg"),
    w: int = Query(256, ge=8, le=4096, description="缩略图最大宽度"),
    h: Optional[int] = Query(None, ge=8, le=4096, description="缩略图最大高度，可选，默认等比根据 w 计算"),
    fmt: str = Query("webp", description="输出格式：webp/png/jpeg"),
    q: int = Query(75, ge=1, le=95, description="压缩质量(仅 webp/jpeg 有效)"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """返回图片缩略图。

    首次请求会生成并缓存缩略图（本地：`/.thumbnails`；S3：`thumbnails/`），
    后续请求直接命中缓存，避免重复生成。
    """
    return thumbnail_service.get_or_create(db, storage_id=storage_id, path=path, width=w, height=h, fmt=fmt, quality=q)


@router.post("/folders", response_model=FilesMutationResponse)
def create_folder(
    request: Request,
    payload: FolderCreateBody,
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(..., description="父目录路径"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        # 直接调用存储后端，避免环境差异导致服务方法不可见；随后写入目录表
        backend = file_service._get_backend(db, storage_id=storage_id)
        resp = backend.mkdir(parent=path, name=payload.name)
        # 写入 directory_entries
        try:
            from app.packages.system.crud.directory_entry import directory_entry_crud
            from app.packages.system.models.directory_entry import DirectoryEntry

            folder_name = None
            if isinstance(resp, dict):
                data = resp.get("data") or {}
                if isinstance(data, dict):
                    folder_name = data.get("folder_name")
            if folder_name:
                par = (path or "/").strip() or "/"
                if not par.startswith("/"):
                    par = "/" + par
                if not par.endswith("/"):
                    par = par + "/"
                full_path = (par + folder_name).rstrip("/")
                exists = (
                    directory_entry_crud
                    .query(db)
                    .filter(DirectoryEntry.storage_id == storage_id)
                    .filter(DirectoryEntry.path == full_path)
                    .first()
                )
                if exists is None:
                    directory_entry_crud.create(db, {"storage_id": storage_id, "path": full_path})
        except Exception:
            pass
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="create",
            class_method="app.packages.system.api.v1.endpoints.files.create_folder",
            request_body={"storage_id": storage_id, "path": path, "name": payload.name},
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.patch("/files", response_model=FilesMutationResponse)
def rename(
    request: Request,
    payload: RenameBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        backend = file_service._get_backend(db, storage_id=storage_id)
        resp = backend.rename(old_path=payload.oldPath, new_path=payload.newPath)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.files.rename",
            request_body={"storage_id": storage_id, "old_path": payload.oldPath, "new_path": payload.newPath},
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/files/move", response_model=FilesMutationResponse)
def move(
    request: Request,
    payload: MoveCopyBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        backend = file_service._get_backend(db, storage_id=storage_id)
        resp = backend.move(source_paths=payload.sourcePaths, destination_path=payload.destinationPath)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.files.move",
            request_body={
                "storage_id": storage_id,
                "source_paths": payload.sourcePaths,
                "destination_path": payload.destinationPath,
            },
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/files/copy", response_model=FilesMutationResponse)
def copy(
    request: Request,
    payload: MoveCopyBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        backend = file_service._get_backend(db, storage_id=storage_id)
        resp = backend.copy(source_paths=payload.sourcePaths, destination_path=payload.destinationPath)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="create",
            class_method="app.packages.system.api.v1.endpoints.files.copy",
            request_body={
                "storage_id": storage_id,
                "source_paths": payload.sourcePaths,
                "destination_path": payload.destinationPath,
            },
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.delete("/files", response_model=FilesMutationResponse)
def delete_items(
    request: Request,
    payload: DeleteBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    resp: Optional[Any] = None

    try:
        backend = file_service._get_backend(db, storage_id=storage_id)
        resp = backend.delete(paths=payload.paths)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="delete",
            class_method="app.packages.system.api.v1.endpoints.files.delete_items",
            request_body={"storage_id": storage_id, "paths": payload.paths},
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/files/clipboard", response_model=FilesMutationResponse)
def set_clipboard(
    request: Request,
    payload: ClipboardSetBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    # create_response 返回的是 dict，这里统一用 Any 以便日志摘要函数复用
    resp: Optional[Any] = None

    try:
        # 仅校验存储是否存在
        _ = file_service._get_backend(db, storage_id=storage_id)
        clip = clipboard_service.set(current_user.id, action=payload.action, storage_id=storage_id, paths=payload.paths)
        resp = create_response("剪贴板已更新", clip, HTTP_STATUS_OK)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="other",
            class_method="app.packages.system.api.v1.endpoints.files.set_clipboard",
            request_body={"storage_id": storage_id, "action": payload.action, "paths": payload.paths},
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.get("/files/clipboard", response_model=ClipboardGetResponse)
def get_clipboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    clip = clipboard_service.get(current_user.id)
    return create_response("获取剪贴板成功", clip, HTTP_STATUS_OK)


@router.delete("/files/clipboard", response_model=FilesMutationResponse)
def clear_clipboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    # 这里 resp 同样可能是 dict
    resp: Optional[Any] = None

    try:
        clipboard_service.clear(current_user.id)
        resp = create_response("剪贴板已清空", None, HTTP_STATUS_OK)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="other",
            class_method="app.packages.system.api.v1.endpoints.files.clear_clipboard",
            request_body=None,
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


@router.post("/files/paste", response_model=FilesMutationResponse)
def paste(
    request: Request,
    storage_id: int = Query(..., alias="storageId"),
    destination_path: str = Query(..., alias="destinationPath"),
    clear_after: bool = Query(True, alias="clearAfter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    started_at = tz_now()
    status = "success"
    error_message: Optional[str] = None
    # paste 返回的可能是后端字典响应或 FastAPI Response
    resp: Optional[Any] = None

    try:
        clip = clipboard_service.get(current_user.id)
        if not clip:
            resp = create_response("剪贴板为空", None, HTTP_STATUS_OK)
            return resp
        if int(clip.get("storage_id") or -1) != storage_id:
            from app.packages.system.core.constants import HTTP_STATUS_BAD_REQUEST
            resp = create_response("剪贴板与目标存储不一致", None, HTTP_STATUS_BAD_REQUEST)
            return resp

        action = (clip.get("action") or "copy").lower()
        paths = clip.get("paths") or []
        if not paths:
            resp = create_response("剪贴板无路径", None, HTTP_STATUS_OK)
            return resp

        backend = file_service._get_backend(db, storage_id=storage_id)
        if action == "copy":
            resp = backend.copy(source_paths=paths, destination_path=destination_path)
        else:  # cut -> move
            resp = backend.move(source_paths=paths, destination_path=destination_path)

        if clear_after:
            clipboard_service.clear(current_user.id)
        return resp
    except Exception as exc:
        status = "failure"
        error_message = str(exc)
        raise
    finally:
        _record_operation_log(
            db=db,
            request=request,
            current_user=current_user,
            business_type="update",
            class_method="app.packages.system.api.v1.endpoints.files.paste",
            request_body={
                "storage_id": storage_id,
                "destination_path": destination_path,
                "clear_after": clear_after,
            },
            response_body=_summarize_response(resp),
            status=status,
            error_message=error_message,
            started_at=started_at,
        )


def _record_operation_log(
    *,
    db: Session,
    request: Request,
    current_user: User,
    business_type: str,
    class_method: str,
    request_body: Optional[dict[str, Any]],
    response_body: Optional[dict[str, Any]],
    status: str,
    error_message: Optional[str],
    started_at: datetime,
) -> None:
    """记录文件管理相关操作日志。"""

    finished_at = tz_now()
    cost_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
    status_value = status if status in {"success", "failure"} else "other"

    try:
        log_service.record_operation_log(
            db,
            payload={
                "module": "文件管理",
                "business_type": business_type,
                "operator_name": current_user.username,
                "operator_department": None,
                "operator_ip": _extract_client_ip(request),
                "operator_location": None,
                "request_method": request.method,
                "request_uri": _build_request_uri(request),
                "class_method": class_method,
                "request_params": _safe_json_dump(request_body),
                "response_params": _safe_json_dump(response_body),
                "status": status_value,
                "error_message": error_message,
                "cost_ms": cost_ms,
                "operate_time": finished_at,
            },
        )
    except Exception as exc:  # pragma: no cover - 防御性记录
        logger.warning("Failed to record file operation log: %s", exc)


def _extract_client_ip(request: Request) -> Optional[str]:
    for header in ("x-forwarded-for", "x-real-ip", "x-client-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _safe_json_dump(payload: Optional[dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"unserializable": True}, ensure_ascii=False)


def _build_request_uri(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path


def _summarize_response(resp: Optional[Any]) -> Optional[dict[str, Any]]:
    if resp is None:
        return None
    # FastAPI Response
    status_code = getattr(resp, "status_code", None)
    if isinstance(status_code, int):
        return {"status_code": status_code}
    # dict payload from create_response
    if isinstance(resp, dict):
        code = resp.get("code")
        msg = resp.get("msg")
        return {"code": code, "msg": msg}
    return None
