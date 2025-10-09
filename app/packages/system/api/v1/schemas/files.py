"""文件管理 - 文件/文件夹 操作请求/响应模型。"""

from typing import Optional

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
FilesMutationResponse = ResponseEnvelope[dict | list | None]

