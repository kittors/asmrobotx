"""通用响应封装模型。"""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    """系统统一的响应外层结构。"""

    msg: str
    data: Optional[T] = None
    code: int
    meta: Optional[Dict[str, Any]] = None
