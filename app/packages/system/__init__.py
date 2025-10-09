"""系统业务包，对应原始的用户与权限系统实现。"""

from app.packages.types import AppPackage

from .api.v1 import api_router
from .core.config import get_settings
from .core.exceptions import generic_exception_handler, http_exception_handler
from .core.logger import logger, setup_logging
from .core.responses import create_response
from .db.init_db import init_db

package = AppPackage(
    name="system",
    api_router=api_router,
    get_settings=get_settings,
    setup_logging=setup_logging,
    logger=logger,
    init_db=init_db,
    create_response=create_response,
    http_exception_handler=http_exception_handler,
    generic_exception_handler=generic_exception_handler,
)

__all__ = ["package", "api_router", "get_settings"]
