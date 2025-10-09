"""文件与文件夹操作路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.files import (
    DeleteBody,
    FilesListResponse,
    FilesMutationResponse,
    FolderCreateBody,
    MoveCopyBody,
    RenameBody,
)
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.core.responses import create_response
from app.packages.system.core.constants import HTTP_STATUS_OK
from app.packages.system.models.user import User
from app.packages.system.services.file_service import file_service

router = APIRouter(tags=["files"])


@router.get("/files", response_model=FilesListResponse)
def list_items(
    storage_id: int = Query(..., alias="storageId"),
    path: Optional[str] = Query("/"),
    file_type: Optional[str] = Query(None, alias="fileType"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.list_items(db, storage_id=storage_id, path=path, file_type=file_type, search=search)


@router.post("/files", response_model=FilesMutationResponse)
async def upload_files(
    storage_id: int = Query(..., alias="storageId"),
    path: Optional[str] = Query("/"),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    results = await file_service.upload(db, storage_id=storage_id, path=path, files=files)
    return create_response("上传完成", results, HTTP_STATUS_OK)


@router.get("/files/download")
def download_file(
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.download(db, storage_id=storage_id, path=path)


@router.get("/files/preview")
def preview_file(
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.preview(db, storage_id=storage_id, path=path)


@router.post("/folders", response_model=FilesMutationResponse)
def create_folder(
    payload: FolderCreateBody,
    storage_id: int = Query(..., alias="storageId"),
    path: str = Query(..., description="父目录路径"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.mkdir(db, storage_id=storage_id, parent=path, name=payload.name)


@router.patch("/files", response_model=FilesMutationResponse)
def rename(
    payload: RenameBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.rename(db, storage_id=storage_id, old_path=payload.oldPath, new_path=payload.newPath)


@router.post("/files/move", response_model=FilesMutationResponse)
def move(
    payload: MoveCopyBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.move(db, storage_id=storage_id, source_paths=payload.sourcePaths, destination_path=payload.destinationPath)


@router.post("/files/copy", response_model=FilesMutationResponse)
def copy(
    payload: MoveCopyBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.copy(db, storage_id=storage_id, source_paths=payload.sourcePaths, destination_path=payload.destinationPath)


@router.delete("/files", response_model=FilesMutationResponse)
def delete_items(
    payload: DeleteBody,
    storage_id: int = Query(..., alias="storageId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return file_service.delete(db, storage_id=storage_id, paths=payload.paths)

