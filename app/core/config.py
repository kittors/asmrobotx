"""配置模块：负责加载和缓存基于环境变量的应用设置。"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 探测项目根目录并按优先级加载第一个可用的环境文件，保证本地环境可以覆盖默认配置。 
# 一旦找到 `.env`、`.env.development` 或 `.env.production` 中的任意一个就停止继续查找。
BASE_DIR = Path(__file__).resolve().parents[2]
for candidate in (".env", ".env.development", ".env.production"):
    env_path = BASE_DIR / candidate
    if env_path.exists():
        load_dotenv(env_path, override=False, encoding="utf-8")
        break


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
    app_port: int = Field(default=8000, alias="APP_PORT")

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


@lru_cache
def get_settings() -> Settings:
    """返回单例化的配置对象，避免重复解析环境变量造成性能浪费。"""
    return Settings()
