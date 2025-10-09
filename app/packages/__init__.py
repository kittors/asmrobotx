"""业务包注册中心：集中管理项目中可用的业务模块。"""

from __future__ import annotations

import os
from typing import Dict

from . import system
from .types import AppPackage

PACKAGE_REGISTRY: Dict[str, AppPackage] = {
    system.package.name: system.package,
}


def get_active_package() -> AppPackage:
    """根据 ``APP_ACTIVE_PACKAGE`` 环境变量选择当前启用的业务包。"""
    package_name = os.getenv("APP_ACTIVE_PACKAGE", system.package.name)
    try:
        return PACKAGE_REGISTRY[package_name]
    except KeyError as exc:
        available = ", ".join(PACKAGE_REGISTRY)
        raise RuntimeError(
            f"未找到名为 '{package_name}' 的业务包，可用选项：{available}"
        ) from exc


__all__ = ["system", "PACKAGE_REGISTRY", "get_active_package"]
