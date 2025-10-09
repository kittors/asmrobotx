# 日志管理 API

提供操作日志与登录日志的后台管理能力，支持查询、详情、导出与清理。

> **关于监听规则**：只有命中且处于启用状态的规则才会写入操作日志，所有匹配逻辑均基于数据库中的 `operation_log_monitor_rules` 配置表。可按请求 URI 与 HTTP 方法控制采集范围，避免在日志管理等敏感路径上形成递归记录。

## 操作日志

### 查询操作日志列表

- **URL**：`GET /api/v1/logs/operations`
- **认证**：需要授权
- **查询参数**：
  - `module`：系统模块模糊查询
  - `operator_name`：操作人员模糊查询
  - `operator_ip`：操作地址/IP 模糊查询
  - `operation_types`：操作类型（可多选，取值：`新增`、`修改`、`删除`、`授权`、`导出`、`导入`、`强退`、`清除数据`、`其他` 或对应英文枚举）
  - `statuses`：操作状态（可多选，`成功` 或 `失败`，支持英文 `success` / `failure`）
  - `request_uri`：请求地址模糊查询
  - `start_time`/`end_time`：操作时间范围，格式 `YYYY-MM-DD HH:MM:SS`
  - `page`/`page_size`：分页控制
- **额外说明**：仅当请求命中启用的监听规则时才会写入操作日志；禁用规则会阻止新记录产生，但历史数据仍会在列表中展示。
- **响应示例**：

```json
{
  "code": 200,
  "msg": "获取操作日志成功",
  "data": {
    "total": 1,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "log_number": "20250930160526000000",
        "module": "服务记录管理",
        "operation_type": "修改",
        "operation_type_code": "update",
        "operator_name": "admin",
        "operator_ip": "183.161.76.183",
        "request_uri": "/prod-api/system/serviceRecord",
        "status": "成功",
        "status_code": "success",
        "operate_time": "2025-09-30 16:05:26",
        "cost_ms": 42
      }
    ]
  }
}
```

### 查询操作日志详情

- **URL**：`GET /api/v1/logs/operations/{log_number}`
- **响应字段**：包含登录信息、请求信息、模块/类型、类方法、请求/返回参数、状态、耗时与操作时间等。

### 删除单条操作日志

- **URL**：`DELETE /api/v1/logs/operations/{log_number}`
- **说明**：软删除指定日志记录。

### 清除全部操作日志

- **URL**：`DELETE /api/v1/logs/operations`
- **说明**：将所有操作日志标记为删除，列表中不再展示。

### 导出操作日志

- **URL**：`GET /api/v1/logs/operations/export`
- **说明**：按照查询条件导出 xlsx 文件，表头包含日志编号、系统模块、操作类型、操作人员、操作地址、请求地址、操作状态、操作时间与消耗时间。

## 登录日志

### 查询登录日志列表

- **URL**：`GET /api/v1/logs/logins`
- **认证**：需要授权
- **查询参数**：
  - `username`：用户名模糊查询
  - `ip_address`：登录地址/IP 模糊查询
  - `statuses`：登录状态（`成功` / `失败` 或英文枚举）
  - `start_time`/`end_time`：登录时间范围，格式 `YYYY-MM-DD HH:MM:SS`
  - `page`/`page_size`：分页控制
- **响应字段**：包含访问编号、用户名、客户端、设备类型、地址、登录地点、操作系统、浏览器、登录状态、描述与访问时间。

> 登录接口会自动写入成功与失败的登录行为，字段来源于请求头部（如 `User-Agent`、`X-Forwarded-For` 等）。

### 删除登录日志

- **URL**：`DELETE /api/v1/logs/logins/{visit_number}`

### 清除全部登录日志

- **URL**：`DELETE /api/v1/logs/logins`

## 序列生成

服务层 `log_service` 暴露 `generate_operation_number` 与 `generate_visit_number` 方法，可用于按照 `时间戳 + 微秒` 规则生成 20 位纯数字编号，保证唯一性。

## 监听规则维护

`operation_log_monitor_rules` 支持以下核心字段：

- `request_uri` / `match_mode`：用于描述匹配策略，支持 `exact` 精确匹配与 `prefix` 前缀匹配；
- `http_method`：HTTP 方法，`ALL` 表示对所有方法生效；
- `is_enabled`：控制是否采集与展示命中的请求；
- `operation_type_code`：可自定义的业务类型编码（如 `create`、`update`、`query` 等，标签可通过字典 `operation_log_type` 获取）；
- `description`：规则用途说明。

默认会预置一条禁用 `/api/v1/logs/operations` 前缀的规则，避免日志管理接口互相记录。若希望采集该接口的访问，需要手动将规则启用；其它业务接口亦需新增并启用对应的规则才会产生操作日志。

### 接口

- `GET /api/v1/logs/monitor-rules`
  - **说明**：分页查询监听规则，支持按 URI、HTTP 方法、匹配模式、启用状态以及类型编码过滤。
  - **查询参数**：
    - `request_uri`：URI 关键词模糊匹配；
    - `http_method`：HTTP 方法，大小写不敏感；
    - `match_mode`：`exact` 或 `prefix`；
    - `is_enabled`：布尔值，过滤启用/禁用规则；
    - `operation_type_code`：自定义的类型编码；
    - `page`/`page_size`：分页参数，默认 1/20。
  - **响应示例**：

    ```json
    {
      "code": 200,
      "msg": "获取监听规则列表成功",
      "data": {
        "total": 1,
        "page": 1,
        "page_size": 20,
        "items": [
          {
            "id": 3,
            "name": "日志接口自审计屏蔽",
            "request_uri": "/api/v1/logs/operations",
            "http_method": "ALL",
            "match_mode": "prefix",
            "is_enabled": false,
            "description": "避免记录日志管理接口自身触发的操作日志",
            "operation_type_code": "query",
            "operation_type_label": "查询",
            "create_time": "2024-05-18 09:30:15",
            "update_time": "2024-05-18 09:30:15"
          }
        ]
      }
    }
    ```

- `POST /api/v1/logs/monitor-rules`
  - **说明**：新增监听规则。
  - **请求体字段**：
    - `request_uri` *(必填)*：需要匹配的 URI；
    - `http_method` *(默认 `ALL`)*：HTTP 方法；
    - `match_mode` *(默认 `exact`)*：`exact` 精确匹配 或 `prefix` 前缀匹配；
    - `is_enabled` *(默认 `true`)*：布尔值，是否启用；
    - `name`、`description`：可选的说明信息；
    - `operation_type_code`：自定义类型编码（标签可通过字典数据映射）。
  - **请求示例**：

    ```json
    {
      "name": "接口导出不记录",
      "request_uri": "/api/v1/report/export",
      "http_method": "POST",
      "match_mode": "prefix",
      "is_enabled": false,
      "operation_type_code": "export",
      "description": "报表导出不需要记录操作日志"
    }
    ```
  - **成功响应**：返回创建后的规则详情（同列表项结构），`code` 为 201。

- `GET /api/v1/logs/monitor-rules/{rule_id}`
  - **说明**：按主键获取单条规则详情。
  - **响应结构**：`data` 为单个规则对象，字段与列表项一致。

- `PUT /api/v1/logs/monitor-rules/{rule_id}`
  - **说明**：更新规则；请求体支持部分字段，未提供的字段保持不变。
  - **请求示例**：

    ```json
    {
      "is_enabled": true
    }
    ```
  - **响应**：返回更新后的规则详情。

- `DELETE /api/v1/logs/monitor-rules/{rule_id}`
  - **说明**：软删除规则，响应 `data` 包含 `{ "rule_id": <id> }`。

在管理界面或调用上述接口时，可自由维护类型编码与中文名称，满足本地化或扩展需求。所有接口统一返回 `code`、`msg`、`data` 结构，并可能在 `meta` 字段返回刷新后的访问令牌（若存在）。
