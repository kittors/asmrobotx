"""系统字典服务：提供统一的字典类型与字典项管理能力。"""

from __future__ import annotations

import re
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
from app.packages.system.crud.dictionary import dictionary_crud
from app.packages.system.crud.dictionary_type import dictionary_type_crud
from app.packages.system.models.dictionary import DictionaryEntry, DictionaryType

_TYPE_CODE_PATTERN = re.compile(r"^[a-z0-9_]+$")


class DictionaryService:
    """封装系统字典相关的业务逻辑。"""

    # ------------------------------------------------------------------
    # 字典类型管理
    # ------------------------------------------------------------------

    def list_types(self, db: Session, *, keyword: Optional[str] = None) -> Dict[str, Any]:
        """返回所有未删除的字典类型，可根据关键字过滤。"""
        types = dictionary_type_crud.list_with_keyword(db, keyword=keyword)
        data = [self._serialize_type(item) for item in types]
        return create_response("获取字典类型成功", data, HTTP_STATUS_OK)

    def create_type(
        self,
        db: Session,
        *,
        type_code: str,
        display_name: str,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Dict[str, Any]:
        """创建新的字典类型。"""
        normalized_code = self._normalize_type_code(type_code)
        normalized_display_name = self._normalize_required_text(display_name, "显示名称")
        normalized_description = self._normalize_optional_text(description)
        normalized_sort_order = self._normalize_sort_order(sort_order)

        existing = dictionary_type_crud.get_by_code(db, normalized_code, include_deleted=True)
        if existing is not None:
            raise AppException("字典类型编码已存在", HTTP_STATUS_CONFLICT)

        created = dictionary_type_crud.create(
            db,
            {
                "type_code": normalized_code,
                "display_name": normalized_display_name,
                "description": normalized_description,
                "sort_order": normalized_sort_order,
            },
        )
        return create_response("创建字典类型成功", self._serialize_type(created), HTTP_STATUS_OK)

    def update_type(
        self,
        db: Session,
        *,
        type_code: str,
        display_name: str,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Dict[str, Any]:
        """更新既有字典类型的展示信息。"""
        dictionary_type = dictionary_type_crud.get_by_code(db, type_code)
        if dictionary_type is None:
            raise AppException("字典类型不存在或已删除", HTTP_STATUS_NOT_FOUND)

        dictionary_type.display_name = self._normalize_required_text(display_name, "显示名称")
        dictionary_type.description = self._normalize_optional_text(description)
        if sort_order is not None:
            dictionary_type.sort_order = self._normalize_sort_order(sort_order)

        saved = dictionary_type_crud.save(db, dictionary_type)
        return create_response("更新字典类型成功", self._serialize_type(saved), HTTP_STATUS_OK)

    def delete_type(self, db: Session, *, type_code: str) -> Dict[str, Any]:
        """软删除字典类型及其下所有字典项。"""
        dictionary_type = dictionary_type_crud.get_by_code(db, type_code)
        if dictionary_type is None:
            raise AppException("字典类型不存在或已删除", HTTP_STATUS_NOT_FOUND)

        affected_items = dictionary_crud.soft_delete_by_type(db, type_code=type_code)
        dictionary_type_crud.soft_delete(db, dictionary_type)

        payload = {
            "type_code": type_code,
            "deleted_items": affected_items,
        }
        return create_response("删除字典类型成功", payload, HTTP_STATUS_OK)

    # ------------------------------------------------------------------
    # 字典项管理
    # ------------------------------------------------------------------

    def list_by_type(
        self,
        db: Session,
        *,
        type_code: str,
        keyword: Optional[str] = None,
        page: int = 1,
        size: int = 10,
        fetch_all: bool = False,
    ) -> Dict[str, Any]:
        """根据类型编码返回字典项列表。

        - 当 `fetch_all` 为 True 时，忽略分页参数并一次性返回所有数据；
        - 否则按 `page/size` 进行分页。
        """
        dictionary_type = dictionary_type_crud.get_by_code(db, type_code)
        if dictionary_type is None:
            raise AppException("字典类型不存在或已删除", HTTP_STATUS_NOT_FOUND)

        if fetch_all:
            # 先获取总数，再一次性取全量（避免固定上限）。
            _, total = dictionary_crud.list_with_filters(
                db,
                type_code=type_code,
                keyword=keyword,
                skip=0,
                limit=1,
            )
            limit = max(total, 1)
            items, _ = dictionary_crud.list_with_filters(
                db,
                type_code=type_code,
                keyword=keyword,
                skip=0,
                limit=limit,
            )
            payload = {
                "total": total,
                "page": 1,
                "size": total,
                "list": [self._serialize_item(item) for item in items],
            }
            return create_response("获取字典项成功", payload, HTTP_STATUS_OK)

        normalized_page = max(page, 1)
        normalized_size = max(min(size, 200), 1)
        skip = (normalized_page - 1) * normalized_size

        items, total = dictionary_crud.list_with_filters(
            db,
            type_code=type_code,
            keyword=keyword,
            skip=skip,
            limit=normalized_size,
        )

        payload = {
            "total": total,
            "page": normalized_page,
            "size": normalized_size,
            "list": [self._serialize_item(item) for item in items],
        }
        return create_response("获取字典项成功", payload, HTTP_STATUS_OK)

    def create_item(
        self,
        db: Session,
        *,
        type_code: str,
        label: str,
        value: str,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Dict[str, Any]:
        """在指定类型下新增字典项。"""
        dictionary_type = dictionary_type_crud.get_by_code(db, type_code)
        if dictionary_type is None:
            raise AppException("字典类型不存在或已删除", HTTP_STATUS_NOT_FOUND)

        normalized_label = self._normalize_required_text(label, "显示文本")
        normalized_value = self._normalize_required_text(value, "实际值")
        normalized_description = self._normalize_optional_text(description)
        normalized_sort_order = self._normalize_sort_order(sort_order)

        existing = dictionary_crud.get_by_value(
            db,
            type_code=type_code,
            value=normalized_value,
            include_deleted=True,
        )
        if existing is not None:
            raise AppException("字典值在该类型下已存在", HTTP_STATUS_CONFLICT)

        created = dictionary_crud.create(
            db,
            {
                "type_code": dictionary_type.type_code,
                "label": normalized_label,
                "value": normalized_value,
                "description": normalized_description,
                "sort_order": normalized_sort_order,
            },
        )
        return create_response("创建字典项成功", self._serialize_item(created), HTTP_STATUS_OK)

    def update_item(
        self,
        db: Session,
        *,
        item_id: int,
        label: str,
        value: str,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Dict[str, Any]:
        """修改既有字典项的信息。"""
        dictionary_item = dictionary_crud.get(db, item_id)
        if dictionary_item is None:
            raise AppException("字典项不存在或已删除", HTTP_STATUS_NOT_FOUND)

        dictionary_type = dictionary_type_crud.get_by_code(db, dictionary_item.type_code)
        if dictionary_type is None:
            raise AppException("关联的字典类型不存在或已删除", HTTP_STATUS_NOT_FOUND)

        normalized_label = self._normalize_required_text(label, "显示文本")
        normalized_value = self._normalize_required_text(value, "实际值")
        normalized_description = self._normalize_optional_text(description)

        existing = dictionary_crud.get_by_value(
            db,
            type_code=dictionary_item.type_code,
            value=normalized_value,
            exclude_id=dictionary_item.id,
            include_deleted=True,
        )
        if existing is not None:
            raise AppException("字典值在该类型下已存在", HTTP_STATUS_CONFLICT)

        dictionary_item.label = normalized_label
        dictionary_item.value = normalized_value
        dictionary_item.description = normalized_description
        if sort_order is not None:
            dictionary_item.sort_order = self._normalize_sort_order(sort_order)

        saved = dictionary_crud.save(db, dictionary_item)
        return create_response("更新字典项成功", self._serialize_item(saved), HTTP_STATUS_OK)

    def delete_item(self, db: Session, *, item_id: int) -> Dict[str, Any]:
        """软删除指定的字典项。"""
        dictionary_item = dictionary_crud.get(db, item_id)
        if dictionary_item is None:
            raise AppException("字典项不存在或已删除", HTTP_STATUS_NOT_FOUND)

        dictionary_crud.soft_delete(db, dictionary_item)
        return create_response("删除字典项成功", {"id": item_id}, HTTP_STATUS_OK)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _normalize_type_code(self, type_code: str) -> str:
        trimmed = (type_code or "").strip()
        if not trimmed:
            raise AppException("类型编码不能为空", HTTP_STATUS_BAD_REQUEST)
        if not _TYPE_CODE_PATTERN.fullmatch(trimmed):
            raise AppException("类型编码仅支持小写字母、数字与下划线", HTTP_STATUS_BAD_REQUEST)
        return trimmed

    def _normalize_required_text(self, value: str, field_name: str) -> str:
        trimmed = (value or "").strip()
        if not trimmed:
            raise AppException(f"{field_name}不能为空", HTTP_STATUS_BAD_REQUEST)
        return trimmed

    def _normalize_optional_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    def _normalize_sort_order(self, value: Optional[int]) -> int:
        if value is None:
            return 0
        try:
            numeric = int(value)
        except (TypeError, ValueError) as exc:
            raise AppException("排序值必须为整数", HTTP_STATUS_BAD_REQUEST) from exc
        return max(numeric, 0)

    def _serialize_type(self, dictionary_type: DictionaryType) -> dict[str, Any]:
        return {
            "id": dictionary_type.id,
            "type_code": dictionary_type.type_code,
            "display_name": dictionary_type.display_name,
            "description": dictionary_type.description,
            "sort_order": dictionary_type.sort_order,
            "create_time": format_datetime(dictionary_type.create_time),
            "update_time": format_datetime(dictionary_type.update_time),
        }

    def _serialize_item(self, dictionary_item: DictionaryEntry) -> dict[str, Any]:
        return {
            "id": dictionary_item.id,
            "type_code": dictionary_item.type_code,
            "label": dictionary_item.label,
            "value": dictionary_item.value,
            "description": dictionary_item.description,
            "sort_order": dictionary_item.sort_order,
            "create_time": format_datetime(dictionary_item.create_time),
            "update_time": format_datetime(dictionary_item.update_time),
        }


dictionary_service = DictionaryService()
