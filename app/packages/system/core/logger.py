"""日志配置模块：提供彩色输出能力并统一全局日志格式。"""

import logging
import logging.config
import sys
import json
from datetime import datetime
from contextvars import ContextVar
from typing import Optional

from .config import get_settings


class _TZFormatter(logging.Formatter):
    """Formatter that renders timestamps in Settings.timezone.

    Falls back to ISO-8601 with milliseconds when no datefmt is provided.
    """

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: D401
        tz = get_settings().timezone_info
        dt = datetime.fromtimestamp(record.created, tz)
        if datefmt:
            return dt.strftime(datefmt)
        # e.g. 2025-10-23 16:22:32.123+08:00
        return dt.isoformat(sep=" ", timespec="milliseconds")


class ColorFormatter(_TZFormatter):
    """ANSI 彩色格式化器：根据不同日志级别渲染不同颜色，便于快速辨识。"""

    RESET = "\033[0m"
    COLORS = {
        logging.DEBUG: "\033[36m",   # Cyan
        logging.INFO: "\033[32m",    # Green
        logging.WARNING: "\033[33m", # Yellow
        logging.ERROR: "\033[31m",   # Red
        logging.CRITICAL: "\033[41m",  # Red background
    }

    def __init__(
        self,
        fmt: str,
        datefmt: Optional[str] = None,
        style: str = "%",
        use_colors: Optional[bool] = None,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        if use_colors is None:
            use_colors = sys.stderr.isatty()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """返回格式化后的日志文本，并在终端支持的情况下附加颜色。"""
        message = super().format(record)
        if not self.use_colors:
            return message

        color = self.COLORS.get(record.levelno)
        if not color:
            return message

        return f"{color}{message}{self.RESET}"


class JsonFormatter(_TZFormatter):
    """Structured JSON formatter for logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, datefmt=None),
            "logger": record.name,
            "level": record.levelname,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        # Attach exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Injects request_id from contextvars into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        rid = _request_id_ctx.get()
        setattr(record, "request_id", rid)
        return True


def setup_logging() -> None:
    """初始化日志系统，确保项目所有模块使用统一的输出格式与级别。"""
    settings = get_settings()
    log_dir = settings.log_directory
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = settings.log_file_path

    json_enabled = bool(getattr(settings, "log_json", False))
    formatter_name = "json" if json_enabled else "standard"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": "app.packages.system.core.logger.ColorFormatter",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "plain": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "json": {
                "()": "app.packages.system.core.logger.JsonFormatter",
            },
        },
        "handlers": {
            "default": {
                "level": settings.log_level,
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "filters": ["request_id"],
            },
            "file": {
                "level": settings.log_level,
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": formatter_name if json_enabled else "plain",
                "filename": str(log_file_path),
                "when": "midnight",
                "backupCount": 14,
                "encoding": "utf-8",
                "delay": True,
                "filters": ["request_id"],
            },
        },
        "filters": {
            "request_id": {
                "()": "app.packages.system.core.logger.RequestIdFilter",
            }
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default", "file"],
                "level": settings.log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "level": settings.log_level,
                "handlers": ["default", "file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default", "file"],
                "level": settings.log_level,
                "propagate": False,
            },
            "app": {
                "handlers": ["default", "file"],
                "level": settings.log_level,
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["default", "file"],
            "level": settings.log_level,
        },
    }
    logging.config.dictConfig(logging_config)


logger = logging.getLogger("app")

# Expose request id context helpers
def set_request_id(request_id: Optional[str]) -> None:
    _request_id_ctx.set(request_id)

def get_request_id() -> Optional[str]:
    return _request_id_ctx.get()
