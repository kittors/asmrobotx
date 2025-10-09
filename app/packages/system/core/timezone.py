"""时区工具方法：支持根据配置动态获取当前时区。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from zoneinfo import ZoneInfo

from app.packages.system.core.config import get_settings


def get_timezone() -> ZoneInfo:
    """返回配置指定的时区信息。"""
    return get_settings().timezone_info


def now() -> datetime:
    """返回当前时区的时间。"""
    return datetime.now(get_timezone())


def to_local(value: Optional[datetime]) -> Optional[datetime]:
    """将 ``datetime`` 转换为配置时区，支持处理空值与无时区对象。"""
    if value is None:
        return None
    tz = get_timezone()
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def format_datetime(value: Optional[datetime]) -> Optional[str]:
    """将时间格式化为 ``YYYY-MM-DD HH:MM:SS`` 字符串。"""
    localized = to_local(value)
    if localized is None:
        return None
    return localized.strftime("%Y-%m-%d %H:%M:%S")
