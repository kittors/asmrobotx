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
├── docker-compose.yml           # app + postgres + redis（支持 ENVIRONMENT 切换）
├── Dockerfile
├── requirements.txt
├── .env.development / .env.production / .env
└── README.md
```

## 快速开始

1) 本地虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.development .env   # 可按需修改数据库、Redis、JWT、端口、时区等
```
- 启动开发服务：`uvicorn app.main:app --reload`
- 健康检查：`curl http://127.0.0.1:8000/health`
- 本地文件根目录（可选）：在 `.env` 配置 `LOCAL_FILE_ROOT`（示例：/tmp/asmrobotx-files 或 /data/asmrobotx-files）。若不存在存储源，将基于该目录自动创建“本地存储(默认)”。

2) 启动数据库与缓存（Docker，推荐本地开发）
```bash
docker compose --env-file .env.development up -d db redis
```
- PostgreSQL 默认暴露到 `POSTGRES_HOST_PORT`（开发默认 5433）
- Redis 默认暴露到 `REDIS_HOST_PORT`（开发默认 6380）

3) 启动应用
```bash
# 可通过 APP_ACTIVE_PACKAGE 指定业务包（默认 system）
export ENV_FILE=.env.development
uvicorn app.main:app --reload
# 访问 http://127.0.0.1:8000/docs 查看自动文档
```

4) Docker Compose 部署（全栈）
```bash
docker compose --env-file .env.production up --build
```
- 容器说明：
  - app：启动时执行 `app/packages/system/db/init_db.py`（幂等），并将刷新后的令牌写入响应头 `X-Access-Token`
  - db：首次初始化自动执行 `scripts/db/init` 下脚本（聚合 `01_v1.sql`）
  - redis：可选缓存服务
- 常用操作：
  - 仅依赖：`docker compose --env-file .env.development up -d db redis`
  - 下线：`docker compose --env-file .env.development down`
  - 下线并清空数据：`docker compose --env-file .env.development down -v`

5) 运行测试
```bash
pytest -q
```
- 使用独立 SQLite 测试数据库，自动迁移 + 播种，无需手动准备数据

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
