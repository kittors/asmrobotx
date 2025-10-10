"""配置模块：负责加载和缓存基于环境变量的应用设置。"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 探测项目根目录并加载环境文件，支持通过 ENV_FILE/ENVIRONMENT 定制优先级。
def _detect_base_dir() -> Path:
    """向上遍历目录树，寻找包含 `app` 目录的项目根路径。"""
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / "app").is_dir():
            return candidate
    # 回退到文件所在目录，避免在极端情况下抛异常
    return current.parent


BASE_DIR = _detect_base_dir()


def _as_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_environment() -> None:
    env_file_override = os.getenv("ENV_FILE")
    if env_file_override:
        candidate = BASE_DIR / env_file_override
        if candidate.exists():
            load_dotenv(candidate, override=True, encoding="utf-8")
        return

    base_env = BASE_DIR / ".env"
    if base_env.exists():
        load_dotenv(base_env, override=False, encoding="utf-8")

    environment = os.getenv("ENVIRONMENT")
    if environment is None and _as_bool(os.getenv("DEBUG")):
        environment = "development"

    if environment:
        if environment.startswith(".env"):
            candidate_name = environment
        else:
            candidate_name = f".env.{environment}"
        candidate_path = BASE_DIR / candidate_name
        if candidate_path.exists():
            load_dotenv(candidate_path, override=True, encoding="utf-8")


_load_environment()


class Settings(BaseSettings):
    """
    封装应用运行所需的所有配置项，每个字段都可以通过环境变量重写。
    该类支持被 FastAPI 及其它模块直接注入使用，避免在代码中散落魔法字符串。
    """

    project_name: str = Field(default="ASM RobotX API", alias="PROJECT_NAME")
    api_v1_str: str = Field(default="/api/v1", alias="API_V1_STR")
    debug: bool = Field(default=False, alias="DEBUG")

    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_user: str = Field(default="postgres", alias="DATABASE_USER")
    database_password: str = Field(default="postgres", alias="DATABASE_PASSWORD")
    database_name: str = Field(default="asmrobotx", alias="DATABASE_NAME")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    jwt_secret_key: str = Field(default="changeme", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: str = Field(default="log", alias="LOG_DIR")
    log_file_name: str = Field(default="app.log", alias="LOG_FILE_NAME")
    app_port: int = Field(default=8000, alias="APP_PORT")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")

    # 数据隔离策略配置
    data_scope_default_enabled: bool = Field(default=True, alias="DATA_SCOPE_DEFAULT_ENABLED")
    data_scope_bypass_prefixes_raw: str = Field(
        default=(
            "/api/v1/access-controls,"
            "/api/v1/auth,"
            "/api/v1/users,"
            "/api/v1/roles,"
            "/api/v1/logs,"
            "/api/v1/dictionaries,"
            "/api/v1/storage-configs,"
            "/api/v1/files,"
            "/api/v1/organizations"
        ),
        alias="DATA_SCOPE_BYPASS_PREFIXES",
    )
    data_scope_enforce_prefixes_raw: str = Field(default="", alias="DATA_SCOPE_ENFORCE_PREFIXES")

    model_config = SettingsConfigDict(extra='ignore')

    @property
    def sql_database_url(self) -> str:
        """根据当前设置拼接 PostgreSQL 连接串。"""
        return (
            f"postgresql+psycopg2://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def redis_url(self) -> str:
        """根据当前配置生成 Redis 连接地址。"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def _resolve_path(self, raw: str) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def log_directory(self) -> Path:
        """返回日志目录的绝对路径，支持相对路径配置。"""
        return self._resolve_path(self.log_dir)

    @property
    def log_file_path(self) -> Path:
        """组合日志目录与文件名，得到完整的日志文件路径。"""
        return self.log_directory / self.log_file_name

    @property
    def timezone_info(self) -> ZoneInfo:
        """返回当前配置对应的时区信息，无法解析时回退到 UTC。"""
        try:
            return ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    # -------------------
    # 数据隔离策略帮助方法
    # -------------------
    @property
    def data_scope_bypass_prefixes(self) -> list[str]:
        raw = (self.data_scope_bypass_prefixes_raw or "").strip()
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def data_scope_enforce_prefixes(self) -> list[str]:
        raw = (self.data_scope_enforce_prefixes_raw or "").strip()
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """返回单例化的配置对象，避免重复解析环境变量造成性能浪费。"""
    return Settings()
