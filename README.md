# ASM RobotX Backend

基于 FastAPI 的用户与权限管理后端服务，默认启用 system 包（用户、角色、权限、组织、日志、文件存储等）。项目采用“多业务包”架构，通过 `APP_ACTIVE_PACKAGE` 选择加载的业务包，支持生产可用的部署方式与测试体系。

## 功能特性
- 认证与授权：JWT 登录/注册/登出，密码 Bcrypt 存储，细粒度角色/权限/菜单（访问控制）
- 分配能力：角色-用户分配、角色-组织（数据权限）分配，前端可用多选回显与全量覆盖提交
- 统一规范：统一响应结构与异常处理，开放 `X-Access-Token` 头用于滑动续期
- 数据域隔离：中间件 + 查询助手按“组织 + 角色”附加数据范围，创建时自动补齐审计字段
- 数据层：PostgreSQL + SQLAlchemy ORM，Redis 预留（`Settings.redis_url`），Alembic 依赖已准备
- 部署与初始化：Docker Compose 一键启动依赖，容器首次自动执行 `scripts/db/init` 初始化 SQL
- 日志与审计：操作日志/登录日志、模板导出、时间统一基于 `TIMEZONE`
- 文件与存储：本地存储源管理、文件上传/下载/预览/重命名/移动/复制/删除
- 测试：Pytest 覆盖主要接口（独立 SQLite），启动时自动播种基础数据

## 项目结构
```
.
├── app/
│   ├── main.py                  # FastAPI 入口：装配包、异常、CORS、中间件、路由
│   ├── middleware/
│   │   └── datascope.py         # 将用户组织/角色注入数据域上下文
│   ├── core/
│   │   └── datascope.py         # 数据域上下文与通用查询/默认值助手
│   └── packages/
│       ├── types.py             # 业务包对主应用的接口约定
│       └── system/              # 默认系统包
│           ├── api/v1/
│           │   ├── endpoints/   # auth、users、roles、organizations、files、logs、dictionaries、access_controls、storage_configs
│           │   └── schemas/     # 对应的请求/响应模型
│           ├── core/            # config、logger、responses、exceptions、security、dependencies、timezone、session、constants、enums
│           ├── db/              # session、init_db（含默认数据播种与本地目录变更导入）
│           ├── models/          # user、role、permission、organization、log、dictionary、storage、file_record 等
│           ├── crud/            # 各模型的数据库 CRUD 封装
│           └── services/        # auth、user、role、file、storage、log、access_control、clipboard、dir_log_ingestor
├── scripts/
│   ├── migrate.py               # 迁移脚本占位（后续可接入 Alembic 命令）
│   └── db/init/
│       ├── 01_v1.sql            # 按顺序聚合执行 v1/schema 与 v1/data
│       └── v1/
│           ├── schema/001_schema.sql
│           └── data/001_seed_data.sql
├── tests/
│   ├── conftest.py              # 独立 SQLite 测试库与依赖覆盖
│   └── system/                  # 主要接口用例：auth、users、roles、organizations、dictionaries、logs、file_manager、access_control
├── docs/system/api/             # 系统包接口文档（Markdown）
├── docker-compose.yml           # app + postgres + redis（基础配置）
├── docker-compose.override.yml  # 开发覆盖：热重载 + 依赖自动同步（dev）
├── Dockerfile
├── pyproject.toml            # 项目依赖（uv 管理）
├── .env.development / .env.production / .env
└── README.md
```

## 快速开始

推荐使用 Docker 本地开发（宿主机无需安装 Python/uv）。仓库已提供 `docker-compose.override.yml`，默认开启热重载，并在容器内用 uv 自动同步依赖。

1) 准备环境变量
```bash
cp .env.development .env   # 可按需修改数据库、Redis、JWT、端口、时区等
```

2) 一键启动（含热重载）
```bash
docker compose --env-file .env.development up --build
```
- 首次启动会构建镜像并安装依赖。
- 挂载 `.:/app`，代码改动将触发 uvicorn 热重载。
- 健康检查：`curl http://127.0.0.1:8000/health`
- API 文档：访问 http://127.0.0.1:8000/docs
- 端口：宿主机监听 `APP_PORT`（默认 8000），容器固定监听 8000（compose 端口映射 `${APP_PORT}:8000`）。
 - 环境变量：开发覆盖文件已将数据库和 Redis 指向容器内服务名（`db:5432` / `redis:6379`），并禁用容器内对 `.env*` 的再次加载，避免 `localhost:5433` 之类配置干扰。

## 依赖管理（无需主机安装 uv）

通过提供的脚本直接在 Docker 容器内执行 uv，自动更新项目根目录下的 `pyproject.toml` 与 `uv.lock`（通过绑定挂载生效）。

- 添加运行时依赖：
  - `./scripts/uv add <pkg>`
- 添加开发依赖：
  - `./scripts/uv add --dev <pkg>`
- 移除依赖：
  - `./scripts/uv remove <pkg>`
- 升级依赖并刷新锁：
  - `./scripts/uv lock --upgrade`

注意：
- 若应用容器正在运行，脚本会优先执行 `docker compose exec app uv ...`，依赖会立即安装到当前容器环境，无需重启。
- 若容器未运行，脚本会短暂 `docker compose run --rm app uv ...` 更新依赖文件；此时启动应用时会自动 `uv sync` 安装依赖。
- 记得提交更新的 `pyproject.toml` 与 `uv.lock` 到版本库。

3) 查看日志
- 前台查看所有服务：`docker compose --env-file .env.development up`
- 后台运行查看应用日志：`docker compose logs -f app`
- 多服务合并查看：`docker compose logs -f --tail 200 app db redis`

4) 在容器中运行测试
```bash
docker compose run --rm app sh -c "uv sync --group dev && uv run pytest -q"
```
- 或已启动情况下：`docker compose exec app sh -c "uv sync --group dev && uv run pytest -q"`

5) 仅启动依赖（可选）
```bash
docker compose --env-file .env.development up -d db redis
```
- PostgreSQL 暴露到 `POSTGRES_HOST_PORT`（开发默认 5433）
- Redis 暴露到 `REDIS_HOST_PORT`（开发默认 6380）

6) 本机原生运行（可选，仅当你已安装 uv）
```bash
# 安装 uv（未安装时）
# macOS / Linux：curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell)：iwr https://astral.sh/uv/install.ps1 -UseB | iex

uv sync
export ENV_FILE=.env.development
uv run uvicorn app.main:app --reload
```

## 核心环境变量
- 基础运行：`ENVIRONMENT`、`PROJECT_NAME`、`API_V1_STR`、`DEBUG`
- 数据库：`DATABASE_HOST`、`DATABASE_PORT`、`DATABASE_USER`、`DATABASE_PASSWORD`、`DATABASE_NAME`、`DATABASE_ECHO`
- Redis：`REDIS_HOST`、`REDIS_PORT`、`REDIS_DB`
- 安全：`JWT_SECRET_KEY`、`JWT_ALGORITHM`、`ACCESS_TOKEN_EXPIRE_MINUTES`
- 日志：`LOG_LEVEL`、`LOG_DIR`、`LOG_FILE_NAME`
- 其他：`TIMEZONE`、`APP_PORT`、`ENV_FILE`、`APP_ACTIVE_PACKAGE`

开发环境示例（节选）：
```dotenv
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

## 主要 API（system 包）
| 方法 | 路径 | 描述 |
| --- | --- | --- |
| POST | /api/v1/auth/register | 用户注册 |
| POST | /api/v1/auth/login | 用户登录，返回 JWT Token |
| POST | /api/v1/auth/logout | 退出登录 |
| GET  | /api/v1/users/me | 当前用户信息（需认证） |
| GET  | /api/v1/organizations | 组织机构列表 |
| GET  | /api/v1/organizations/tree | 组织机构树 |
| GET  | /api/v1/access-controls/routers | 动态菜单路由（需认证） |
| GET  | /api/v1/roles/{role_id}/users | 角色已分配用户查询（需认证） |
| PUT  | /api/v1/roles/{role_id}/users | 角色分配用户（需认证） |
| GET  | /api/v1/roles/{role_id}/organizations | 角色已分配组织查询（数据权限，需认证） |
| PUT  | /api/v1/roles/{role_id}/organizations | 角色分配组织（数据权限，需认证） |
| GET  | /api/v1/logs/operations | 操作日志查询（需认证） |
| GET  | /api/v1/logs/logins | 登录日志查询（需认证） |
| ...  | /api/v1/files / storage-configs | 文件与存储管理 |

响应统一格式示例：
```json
{
  "msg": "操作描述",
  "data": {"...": "..."},
  "code": 200,
  "meta": {"access_token": "<可选，刷新后的访问令牌>"}
}
```

详尽接口说明见 `docs/system/api/`。

## 后续扩展
1. 完成 Alembic 迁移脚本，替代手工 SQL 变更
2. 按需接入 Redis 缓存（权限、配置等热点数据）
3. 扩展数据范围模型（如部门层级、细粒度资源），完善授权策略
4. 接入 CI/CD（测试、质量检查、安全扫描）
