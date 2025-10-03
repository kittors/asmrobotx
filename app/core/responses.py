"""响应封装：构建系统统一的返回结构。"""

from typing import Any

from app.core.constants import HTTP_STATUS_OK
from app.core.security import consume_refreshed_token


def create_response(msg: str, data: Any = None, code: int = HTTP_STATUS_OK) -> dict[str, Any]:
    """按照 ``msg``、``data``、``code`` 组合出统一响应体。"""
    payload: dict[str, Any] = {"msg": msg, "data": data, "code": code}
    refreshed_token = consume_refreshed_token()
    if refreshed_token:
        payload["meta"] = {"access_token": refreshed_token}
    return payload
