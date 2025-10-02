"""系统字典服务：提供统一的字典项查询能力。"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.constants import HTTP_STATUS_OK
from app.core.responses import create_response
from app.crud.dictionary import dictionary_crud


class DictionaryService:
    """读取并格式化字典项的数据结构。"""

    def list_by_type(self, db: Session, *, type_code: str) -> Dict[str, Any]:
        entries = dictionary_crud.get_items_by_type(db, type_code)
        data = [
            {
                "id": entry.id,
                "type_code": entry.type_code,
                "label": entry.label,
                "value": entry.value,
                "description": entry.description,
                "sort_order": entry.sort_order,
            }
            for entry in entries
        ]
        return create_response("获取字典项成功", data, HTTP_STATUS_OK)


dictionary_service = DictionaryService()
