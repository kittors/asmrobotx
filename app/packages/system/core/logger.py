"""日志配置模块：提供彩色输出能力并统一全局日志格式。"""

import logging
import logging.config
import sys
from typing import Optional

from .config import get_settings


class ColorFormatter(logging.Formatter):
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


def setup_logging() -> None:
    """初始化日志系统，确保项目所有模块使用统一的输出格式与级别。"""
    settings = get_settings()
    log_dir = settings.log_directory
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = settings.log_file_path

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
        },
        "handlers": {
            "default": {
                "level": settings.log_level,
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
            "file": {
                "level": settings.log_level,
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "plain",
                "filename": str(log_file_path),
                "when": "midnight",
                "backupCount": 14,
                "encoding": "utf-8",
                "delay": True,
            },
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
