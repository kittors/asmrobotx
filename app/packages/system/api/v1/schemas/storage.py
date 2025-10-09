"""文件管理 - 存储源 配套的请求/响应模型。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.packages.system.api.v1.schemas.common import ResponseEnvelope


class StorageConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal["S3", "LOCAL"]


class StorageConfigCreate(StorageConfigBase):
    config_key: Optional[str] = Field(None, min_length=1, max_length=64)
    # S3
    region: Optional[str] = None
    bucket_name: Optional[str] = None
    path_prefix: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    custom_domain: Optional[str] = None
    use_https: Optional[bool] = True
    acl_type: Optional[Literal["private", "public", "custom"]] = "private"
    # LOCAL
    local_root_path: Optional[str] = None


class StorageConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[Literal["S3", "LOCAL"]] = None
    config_key: Optional[str] = Field(None, min_length=1, max_length=64)
    # S3
    region: Optional[str] = None
    bucket_name: Optional[str] = None
    path_prefix: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    custom_domain: Optional[str] = None
    use_https: Optional[bool] = None
    acl_type: Optional[Literal["private", "public", "custom"]] = None
    # LOCAL
    local_root_path: Optional[str] = None


class StorageConfigResponseData(BaseModel):
    id: int
    name: str
    type: Literal["S3", "LOCAL"]
    config_key: Optional[str] = None
    region: Optional[str] = None
    bucket_name: Optional[str] = None
    path_prefix: Optional[str] = None
    endpoint_url: Optional[str] = None
    custom_domain: Optional[str] = None
    use_https: Optional[bool] = None
    acl_type: Optional[str] = None
    local_root_path: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None


StorageConfigListResponse = ResponseEnvelope[list[StorageConfigResponseData]]
StorageConfigMutationResponse = ResponseEnvelope[Optional[StorageConfigResponseData]]
StorageTestResponse = ResponseEnvelope[dict]
