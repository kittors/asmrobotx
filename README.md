# ASM RobotX Backend

基于 FastAPI 的用户与权限管理服务，提供注册、登录、用户信息查询以及组织机构列表等核心能力，并包含生产级部署、日志、缓存预留、统一响应格式及环境配置。

## 功能特性
- JWT 认证的注册 / 登录流程，密码使用 Bcrypt 加密存储
- 用户、角色、权限、组织等核心模型以及多对多关系
- 统一的响应体结构与集中式异常处理
- PostgreSQL + SQLAlchemy ORM，Redis 缓存预留（可在 `Settings.redis_url` 中配置）
- Docker Compose 支持，自动数据库初始化脚本
- Pytest 接口测试覆盖注册、登录、用户信息、组织列表
- 操作/登录日志审计，支持搜索、详情、清理与 Excel 导出

## 项目结构
```
.
├── app/
│   ├── api/                   # FastAPI 路由 & 模型
│   ├── core/                  # 配置、日志、安全、依赖等
│   ├── crud/                  # 数据库 CRUD 封装
│   ├── db/                    # 会话与初始化
│   ├── models/                # SQLAlchemy 模型
│   ├── services/              # 业务服务逻辑
│   └── main.py                # FastAPI 入口
├── scripts/
│   └── db/init/               # PostgreSQL 初始化 SQL
├── tests/                     # Pytest 自动化用例
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
- `app`：FastAPI 服务，启动时自动执行 `app/db/init_db.py` 进行数据初始化
- `db`：PostgreSQL，执行 `scripts/db/init/01_init.sql` 注入基础数据
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
| 变量 | 说明 |
| --- | --- |
| `DATABASE_*` | PostgreSQL 连接信息 |
| `REDIS_*` | Redis 连接信息 |
| `JWT_SECRET_KEY` | JWT 签名密钥 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 基础过期时间（分钟，滑动过期窗口） |
| `LOG_LEVEL` | 日志级别 |
| `APP_PORT` / `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` | Docker 暴露的宿主机端口 |

## 主要 API
| 方法 | 路径 | 描述 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | 用户注册 |
| `POST` | `/api/v1/auth/login` | 用户登录，返回 JWT Token |
| `POST` | `/api/v1/auth/logout` | 退出登录，清理客户端令牌 |
| `GET` | `/api/v1/users/me` | 获取当前用户信息（需认证） |
| `GET` | `/api/v1/organizations` | 获取组织机构列表 |
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

详尽接口文档请参考 `docs/api` 目录下的 Markdown 文件。

## 后续扩展建议
1. 引入 Alembic 进行结构化数据库迁移与版本控制。
2. 接入 Redis 缓存以缓存权限、配置等数据。
3. 丰富权限类型（菜单、数据范围）并实现细粒度授权。
4. 集成 CI/CD 流程，自动运行测试与代码质量检查。
