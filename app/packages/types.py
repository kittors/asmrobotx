"""业务包元数据定义。"""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from typing import Callable

from fastapi import APIRouter


@dataclass(frozen=True)
class AppPackage:
    """描述一个业务包暴露给主应用的必要接口。"""

    name: str
    api_router: APIRouter
    get_settings: Callable[[], object]
    setup_logging: Callable[[], None]
    logger: Logger
    init_db: Callable[[], None]
    create_response: Callable[..., dict]
    http_exception_handler: Callable[..., object]
    generic_exception_handler: Callable[..., object]
