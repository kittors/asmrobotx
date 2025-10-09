# ASM RobotX Backend

基于 FastAPI 的用户与权限管理服务，提供注册、登录、用户信息查询以及组织机构列表等核心能力。当前代码已重构为**多业务包架构**，通过 `app/packages` 统一管理系统包及后续的业务包（例如 ChatBox 等），并包含生产级部署、日志、缓存预留、统一响应格式及环境配置。

## 功能特性
- JWT 认证的注册 / 登录流程，密码使用 Bcrypt 加密存储
- 用户、角色、权限、组织等核心模型以及多对多关系
- 统一的响应体结构与集中式异常处理
- PostgreSQL + SQLAlchemy ORM，Redis 缓存预留（可在 `Settings.redis_url` 中配置）
- Docker Compose 支持，自动数据库初始化脚本
- Pytest 接口测试覆盖注册、登录、用户信息、组织列表
- 操作/登录日志审计，支持搜索、详情、清理与 Excel 导出
- 多包装载机制：主应用按 `APP_ACTIVE_PACKAGE` 选择业务包，默认启用 `system` 包
- 初始化数据播种：应用启动或测试执行时会自动创建默认组织、管理员账号与常用字典项

## 项目结构
```
.
├── app/
│   ├── main.py                # FastAPI 入口，按包动态装配
│   └── packages/
│       ├── types.py           # 业务包对主应用暴露的 Hook 定义
│       └── system/            # 默认系统包，实现用户&权限管理
│           ├── api/           # FastAPI 路由 & Pydantic 模型
│           ├── core/          # 配置、日志、安全、依赖等
│           ├── crud/          # 数据库 CRUD 封装
│           ├── db/            # 会话与初始化（含默认数据播种）
│           ├── models/        # SQLAlchemy 模型
│           └── services/      # 业务服务逻辑
├── scripts/
│   └── db/init/               # PostgreSQL 初始化 SQL（按版本分层）
│       ├── 01_v1.sql          # 聚合执行入口（按顺序包含 v1/schema 与 v1/data）
│       └── v1/
│           ├── schema/        # 表结构、索引、扩展等
│           │   └── 001_schema.sql
│           └── data/          # 基础/演示数据、菜单、字典项等
│               └── 001_seed_data.sql
├── tests/                     # Pytest 自动化用例（按业务包划分，如 tests/system）
├── docs/
│   └── system/api/            # 系统包接口文档（Markdown）
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 本地虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.development .env
```
根据需要修改 `.env` 中的数据库、Redis、JWT 等配置。

### 2. 启动后端依赖（使用 Docker）

在本地开发时，可以仅通过 Docker 启动 PostgreSQL 与 Redis：

```bash
# 使用默认 .env 或指定为开发环境变量
docker compose --env-file .env.development up -d db redis
```

默认会把 PostgreSQL 暴露在 `POSTGRES_HOST_PORT`（`.env.development` 中默认为 5433）
和 Redis 暴露在 `REDIS_HOST_PORT`（默认 6380）。如果这些端口与你本地已有服务冲突，可在 `.env.development` 中修改。

### 3. 启动应用
```bash
# 默认启用 system 包，必要时可通过 APP_ACTIVE_PACKAGE 指定其它业务包
# export APP_ACTIVE_PACKAGE=chatbox
# 如需明确指定环境变量文件，可组合使用 ENV_FILE 或 ENVIRONMENT，
# 例如 export ENV_FILE=.env.development 或 export ENVIRONMENT=development
export ENV_FILE=.env.development
uvicorn app.main:app --reload
```
应用默认监听 `http://127.0.0.1:8000`。

### 4. Docker Compose 部署
Compose 默认读取同目录下的 `.env` 文件做变量替换。你可以：
- 将 `.env.production` 复制为 `.env`，或
- 直接指定 `--env-file`：

```bash
docker compose --env-file .env.production up --build
```

常用变量：
- `APP_PORT`：宿主机暴露的应用端口（默认 8000）
- `POSTGRES_HOST_PORT`：宿主机暴露的 PostgreSQL 端口（默认 5433，避免与本地 5432 冲突）
- `REDIS_HOST_PORT`：宿主机暴露的 Redis 端口（默认 6380）

容器说明：
- `app`：FastAPI 服务，启动时会执行 `app/packages/system/db/init_db.py` 以保证核心数据存在（幂等）
- `db`：PostgreSQL，容器首次初始化时会自动执行 `scripts/db/init` 目录下的 `.sql/.sh`，本项目提供按版本聚合的 `scripts/db/init/01_v1.sql`，内部依次包含 `v1/schema` 与 `v1/data`。
- `redis`：Redis 服务，可按需启用缓存

#### 常用 Docker Compose 操作
- 仅启动数据库与缓存供本地开发：
  ```bash
  docker compose --env-file .env.development up -d db redis
  ```
- 停止并移除容器：
  ```bash
  docker compose --env-file .env.development down
  ```
- 停止并删除数据卷（会清空数据库数据，重新执行初始化脚本）：
  ```bash
  docker compose --env-file .env.development down -v
  # 提醒：删除数据卷后，Postgres 将在下次启动时重新运行初始化脚本（01_v1.sql）
  ```
- 重新构建并启动全部服务：
  ```bash
  docker compose --env-file .env.development up --build
  ```

### 5. 运行测试
```bash
pytest
```
测试使用独立的 SQLite 数据库并自动完成数据准备。

## 核心环境变量
本项目默认提供开发环境示例配置，可直接复制 `.env.development` 为 `.env`。下表列出了所有字段的用途及推荐取值：

- **基础运行**
  - `ENVIRONMENT`：当前环境标识，决定加载 `.env.<ENVIRONMENT>`；默认 `development`。
  - `PROJECT_NAME`：FastAPI 应用标题，默认 `ASM RobotX API`。
  - `API_V1_STR`：API 前缀；默认 `/api/v1`。
  - `DEBUG`：启用 FastAPI Debug 模式，开发环境建议为 `True`。

- **数据库连接**
  - `DATABASE_HOST`：数据库主机名，默认 `localhost`。
  - `DATABASE_PORT`：数据库端口，开发 Docker 环境默认 `5433`。
  - `DATABASE_USER`：数据库用户名，默认 `postgres`。
  - `DATABASE_PASSWORD`：数据库密码，默认 `postgres`。
  - `DATABASE_NAME`：数据库名称，开发环境默认 `asmrobotx_dev`。
  - `DATABASE_ECHO`：若为 `True` 则输出 SQL 语句到日志，方便调试。

- **Redis 配置**
  - `REDIS_HOST`：Redis 主机名，默认 `localhost`。
  - `REDIS_PORT`：Redis 端口，默认 `6380`。
  - `REDIS_DB`：Redis 库索引，默认 `0`。

- **安全参数**
  - `JWT_SECRET_KEY`：JWT 签名密钥，建议每个环境独立设置。
  - `JWT_ALGORITHM`：JWT 签名算法，默认 `HS256`。
  - `ACCESS_TOKEN_EXPIRE_MINUTES`：访问令牌过期时间（分钟），默认 `30`。

- **日志配置**
  - `LOG_LEVEL`：日志级别（如 `DEBUG`、`INFO`），默认 `DEBUG`。
  - `LOG_DIR`：日志目录，默认项目根目录下 `log/`。
  - `LOG_FILE_NAME`：日志文件名，默认 `app.log`。
- **时区**
  - `TIMEZONE`：应用运行时所使用的时区标识，默认 `Asia/Shanghai`。该设置会影响日志审计、导出等接口返回的时间展示。

- **服务端口**
  - `APP_PORT`：应用监听端口，默认 `8000`。
  - `POSTGRES_HOST_PORT`：Docker 暴露的 PostgreSQL 端口，默认 `5433`。
  - `REDIS_HOST_PORT`：Docker 暴露的 Redis 端口，默认 `6380`。

- **其它**
  - `ENV_FILE`：显式指定要加载的环境文件（如 `.env.development`），优先级高于 `ENVIRONMENT`。
  - `APP_ACTIVE_PACKAGE`：指定启用的业务包，默认 `system`。

示例 `.env`（开发环境）：
```dotenv
# Development environment variables
ENVIRONMENT=development
PROJECT_NAME=ASM RobotX API
API_V1_STR=/api/v1
DEBUG=True

DATABASE_HOST=localhost
DATABASE_PORT=5433
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=asmrobotx_dev
DATABASE_ECHO=True

REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0

JWT_SECRET_KEY=devsecretkeychange
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

LOG_LEVEL=DEBUG
LOG_DIR=log
LOG_FILE_NAME=app.log
APP_PORT=8000
POSTGRES_HOST_PORT=5433
REDIS_HOST_PORT=6380
TIMEZONE=Asia/Shanghai
```

## 主要 API
| 方法 | 路径 | 描述 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | 用户注册 |
| `POST` | `/api/v1/auth/login` | 用户登录，返回 JWT Token |
| `POST` | `/api/v1/auth/logout` | 退出登录，清理客户端令牌 |
| `GET` | `/api/v1/users/me` | 获取当前用户信息（需认证） |
| `GET` | `/api/v1/organizations` | 获取组织机构列表 |
| `GET` | `/api/v1/access-controls/routers` | 获取动态菜单路由（需认证） |
| `GET` | `/api/v1/logs/operations` | 查询操作日志（需认证） |
| `GET` | `/api/v1/logs/logins` | 查询登录日志（需认证） |

所有响应遵循统一格式：
```json
{
  "msg": "操作描述",
  "data": {"...": "..."},
  "code": 200,
  "meta": {
    "access_token": "<可选，刷新后的访问令牌>"
  }
}
```

详尽接口文档请参考 `docs/system/api` 目录下的 Markdown 文件。

## 后续扩展建议
1. 引入 Alembic 进行结构化数据库迁移与版本控制。
2. 接入 Redis 缓存以缓存权限、配置等数据。
3. 丰富权限类型（菜单、数据范围）并实现细粒度授权。
4. 集成 CI/CD 流程，自动运行测试与代码质量检查。
