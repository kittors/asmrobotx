"""文件管理 - 文件/文件夹 操作请求/响应模型。"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.packages.system.api.v1.schemas.common import ResponseEnvelope


class FilesListQuery(BaseModel):
    storageId: int = Field(..., ge=1)
    path: Optional[str] = "/"
    fileType: Optional[str] = None  # image/document/spreadsheet/pdf/markdown/all
    search: Optional[str] = None


class FolderCreateBody(BaseModel):
    name: str = Field(..., min_length=1)


class RenameBody(BaseModel):
    oldPath: str
    newPath: str


class MoveCopyBody(BaseModel):
    sourcePaths: list[str]
    destinationPath: str


class DeleteBody(BaseModel):
    paths: list[str]


FilesListResponse = ResponseEnvelope[dict]
FilesMutationResponse = ResponseEnvelope[Any]


# ------------- 剪贴板 / 粘贴 -------------
class ClipboardSetBody(BaseModel):
    action: str = Field(..., pattern=r"^(copy|cut)$")  # copy=复制, cut=剪切(移动)
    paths: list[str] = Field(default_factory=list)


class ClipboardInfo(BaseModel):
    action: str
    storage_id: int
    paths: list[str]
    ts: str


ClipboardGetResponse = ResponseEnvelope[Optional[ClipboardInfo]]
