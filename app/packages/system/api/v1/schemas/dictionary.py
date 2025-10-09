"""系统字典相关的请求与响应模型。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.packages.system.api.v1.schemas.common import ResponseEnvelope


# ---------------------------------------------------------------------------
# 字典类型
# ---------------------------------------------------------------------------


class DictionaryTypeBase(BaseModel):
    """字典类型通用字段。"""

    display_name: str = Field(..., min_length=1, description="类型显示名称")
    description: Optional[str] = Field(default=None, description="类型描述")
    sort_order: int = Field(default=0, ge=0, description="排序值，越小越靠前")

    @model_validator(mode="after")
    def _normalize_display_name(self) -> "DictionaryTypeBase":
        self.display_name = self.display_name.strip()
        if not self.display_name:
            raise ValueError("显示名称不能为空")
        if self.description is not None:
            trimmed = self.description.strip()
            self.description = trimmed or None
        return self


class DictionaryTypeCreateRequest(DictionaryTypeBase):
    """新建字典类型的请求体。"""

    type_code: str = Field(..., min_length=1, description="类型编码，需唯一")

    @model_validator(mode="after")
    def _normalize_type_code(self) -> "DictionaryTypeCreateRequest":
        self.type_code = self.type_code.strip()
        if not self.type_code:
            raise ValueError("类型编码不能为空")
        return self


class DictionaryTypeUpdateRequest(DictionaryTypeBase):
    """更新字典类型的请求体（不包含类型编码）。"""

    sort_order: Optional[int] = Field(default=None, ge=0, description="排序值，可选")

    @model_validator(mode="after")
    def _normalize_optional_sort(self) -> "DictionaryTypeUpdateRequest":
        if self.sort_order is None:
            return self
        self.sort_order = int(self.sort_order)
        if self.sort_order < 0:
            raise ValueError("排序值不能为负数")
        return self


class DictionaryTypeItem(BaseModel):
    """字典类型列表项。"""

    id: int
    type_code: str
    display_name: str
    description: Optional[str]
    sort_order: int
    create_time: Optional[str]
    update_time: Optional[str]


DictionaryTypeListResponse = ResponseEnvelope[List[DictionaryTypeItem]]
DictionaryTypeMutationResponse = ResponseEnvelope[DictionaryTypeItem]


class DictionaryTypeDeletionPayload(BaseModel):
    type_code: str
    deleted_items: int


DictionaryTypeDeletionResponse = ResponseEnvelope[DictionaryTypeDeletionPayload]


# ---------------------------------------------------------------------------
# 字典项
# ---------------------------------------------------------------------------


class DictionaryItemBase(BaseModel):
    """字典项通用字段。"""

    label: str = Field(..., min_length=1, description="显示文本")
    value: str = Field(..., min_length=1, description="实际值")
    description: Optional[str] = Field(default=None, description="说明")
    sort_order: int = Field(default=0, ge=0, description="排序值，越小越靠前")

    @model_validator(mode="after")
    def _normalize_texts(self) -> "DictionaryItemBase":
        self.label = self.label.strip()
        self.value = self.value.strip()
        if not self.label:
            raise ValueError("显示文本不能为空")
        if not self.value:
            raise ValueError("实际值不能为空")
        if self.description is not None:
            trimmed = self.description.strip()
            self.description = trimmed or None
        return self


class DictionaryItemCreateRequest(DictionaryItemBase):
    """新增字典项的请求体。"""

    type_code: str = Field(..., min_length=1, description="所属字典类型编码")

    @model_validator(mode="after")
    def _normalize_type_code(self) -> "DictionaryItemCreateRequest":
        self.type_code = self.type_code.strip()
        if not self.type_code:
            raise ValueError("类型编码不能为空")
        return self


class DictionaryItemUpdateRequest(DictionaryItemBase):
    """更新字典项的请求体。"""

    sort_order: Optional[int] = Field(default=None, ge=0, description="排序值，可选")

    @model_validator(mode="after")
    def _normalize_optional_sort(self) -> "DictionaryItemUpdateRequest":
        if self.sort_order is None:
            return self
        self.sort_order = int(self.sort_order)
        if self.sort_order < 0:
            raise ValueError("排序值不能为负数")
        return self


class DictionaryItem(BaseModel):
    """单个字典项的结构。"""

    id: int
    type_code: str
    label: str
    value: str
    description: Optional[str]
    sort_order: int
    create_time: Optional[str]
    update_time: Optional[str]


class DictionaryItemListPayload(BaseModel):
    """字典项分页列表数据。"""

    total: int
    page: int
    size: int
    list: List[DictionaryItem]


DictionaryItemListResponse = ResponseEnvelope[DictionaryItemListPayload]
DictionaryItemMutationResponse = ResponseEnvelope[DictionaryItem]


class DictionaryItemDeletionPayload(BaseModel):
    id: int


DictionaryItemDeletionResponse = ResponseEnvelope[DictionaryItemDeletionPayload]
