"""响应封装：构建系统统一的返回结构。"""

from typing import Any

from app.core.constants import HTTP_STATUS_OK


def create_response(msg: str, data: Any = None, code: int = HTTP_STATUS_OK) -> dict[str, Any]:
    """按照 ``msg``、``data``、``code`` 组合出统一响应体。"""
    return {"msg": msg, "data": data, "code": code}
