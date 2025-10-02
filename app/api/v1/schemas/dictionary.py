"""系统字典相关的响应模型。"""

from typing import Optional

from pydantic import BaseModel

from app.api.v1.schemas.common import ResponseEnvelope


class DictionaryItem(BaseModel):
    """单个字典条目的结构。"""

    id: int
    type_code: str
    label: str
    value: str
    description: Optional[str] = None
    sort_order: int


DictionaryListResponse = ResponseEnvelope[list[DictionaryItem]]
