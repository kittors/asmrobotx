# 日志管理 API

提供操作日志与登录日志的后台管理能力，支持查询、详情、导出与清理。

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
- **说明**：按照查询条件导出 xlsx 文件，表头包含日志编号、系统模块、操作类型、操作人员、操作地址、操作状态、操作时间与消耗时间。

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

### 删除登录日志

- **URL**：`DELETE /api/v1/logs/logins/{visit_number}`

### 清除全部登录日志

- **URL**：`DELETE /api/v1/logs/logins`

## 序列生成

服务层 `log_service` 暴露 `generate_operation_number` 与 `generate_visit_number` 方法，可用于按照 `时间戳 + 微秒` 规则生成 20 位纯数字编号，保证唯一性。
