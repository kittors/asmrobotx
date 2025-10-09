# 用户管理模块接口说明

所有接口需携带 `Authorization: Bearer <access_token>` 头部，通过后端校验当前会话身份。

## GET `/api/v1/users/me`

获取当前登录用户的综合信息（含组织、角色、权限、昵称与状态）。

### 请求头
- `Authorization: Bearer <access_token>`

### 查询参数
- 无额外查询参数。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取用户信息成功",
  "code": 200,
  "data": {
    "user_id": 1,
    "username": "admin",
    "nickname": "系统管理员",
    "status": "normal",
    "organization": {
      "org_id": 1,
      "org_name": "研发部"
    },
    "roles": ["admin"],
    "permissions": ["edit_self_profile", "manage_users", "view_dashboard"]
  }
}
```

### 异常响应
- `401` 缺少或无效的令牌：
  - 缺少认证信息：`{"msg":"缺少认证信息","data":null,"code":401}`
  - Token 非 `bearer` 类型或解析失败。
- `403` 用户被标记为未激活：`{"msg":"用户未激活","data":null,"code":403}`

---

## GET `/api/v1/users`

分页查询用户列表，支持用户名、状态与创建时间范围过滤。

### 查询参数
- `username` *(可选)*：用户名模糊匹配。
- `statuses` *(可选)*：用户状态数组，支持传入英文代码 `normal` / `disabled` 或中文 `正常` / `停用`。
- `start_time` *(可选)*：创建时间开始，格式 `YYYY-MM-DD HH:MM:SS`。
- `end_time` *(可选)*：创建时间结束，格式 `YYYY-MM-DD HH:MM:SS`。
- `page` *(可选)*：页码，从 `1` 开始，默认 `1`。
- `page_size` *(可选)*：每页数量，默认 `20`，上限 `200`。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取用户列表成功",
  "code": 200,
  "data": {
    "total": 1,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "user_id": 1,
        "username": "admin",
        "nickname": "系统管理员",
        "status": "normal",
        "status_label": "正常",
        "role_ids": [1],
        "role_names": ["admin"],
        "organization": {
          "org_id": 1,
          "org_name": "研发部"
        },
        "remark": null,
        "create_time": "2024-02-01 09:00:00",
        "update_time": "2024-02-01 09:30:00",
        "is_active": true
      }
    ]
  }
}
```

### 异常响应
- `400` 请求参数格式错误。
- `401` 未携带或携带无效的访问令牌。

---

## POST `/api/v1/users`

新增用户并分配角色。

### 请求体字段
- `username` *(必填)*：登录用户名，需唯一。
- `password` *(必填)*：初始密码，至少 6 位。
- `nickname` *(可选)*：用户昵称，留空即 `null`。
- `status` *(可选)*：用户状态，默认 `normal`（正常），可传 `disabled`（停用）。
- `role_ids` *(可选)*：角色 ID 列表，可为空数组。
- `remark` *(可选)*：备注信息。
- `organization_id` *(可选)*：所属组织 ID。

### 成功响应
- 状态码：`200`
- 响应体同用户列表项结构。

### 异常响应
- `400` 参数校验失败或角色/组织不存在。
- `401` 认证失败。
- `409` 用户名重复。

---

## PUT `/api/v1/users/{user_id}`

更新用户昵称、状态、角色、备注及组织。

### 路径参数
- `user_id`：用户主键 ID。

### 请求体字段
- `nickname` *(可选)*：用户昵称。
- `status` *(可选)*：用户状态 `normal` / `disabled`，也接受中文 `正常` / `停用`。
- `role_ids` *(可选)*：角色 ID 列表，传空数组表示清空角色，不传则保持原值。
- `remark` *(可选)*：备注。
- `organization_id` *(可选)*：所属组织 ID，传 `null` 解除绑定。

### 成功响应
- 状态码：`200`
- 响应体同用户列表项结构。

### 异常响应
- `400` 参数校验失败。
- `401` 认证失败。
- `404` 用户不存在或已删除。

---

## DELETE `/api/v1/users/{user_id}`

软删除指定用户。系统预置管理员（用户名 `admin`）不可删除。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "删除用户成功",
  "code": 200,
  "data": {
    "user_id": 12
  }
}
```

### 异常响应
- `400` 系统预置管理员禁止删除。
- `401` 认证失败。
- `404` 用户不存在或已删除。

---

## PUT `/api/v1/users/{user_id}/reset-password`

为指定用户重置密码。

### 请求体字段
- `password` *(必填)*：新密码，至少 6 位。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "重置密码成功",
  "code": 200,
  "data": {
    "user_id": 12
  }
}
```

### 异常响应
- `400` 密码长度不足或参数错误。
- `401` 认证失败。
- `404` 用户不存在或已删除。

---

## GET `/api/v1/users/export`

按条件导出用户列表为 Excel (`.xlsx`) 文件，字段包括用户名称、昵称、状态、角色、创建时间、备注。

### 查询参数
与列表接口一致。

### 成功响应
- 状态码：`200`
- 响应头包含 `Content-Disposition: attachment; filename=users-<timestamp>.xlsx`。

### 异常响应
- `400` 参数校验失败。
- `401` 认证失败。

---

## GET `/api/v1/users/template`

下载批量导入用户的标准模版 (`user-template.xlsx`)，首行含字段标题，第二行提供示例数据。

### 成功响应
- 状态码：`200`
- 响应头包含 `Content-Disposition: attachment; filename=user-template.xlsx`。

---

## POST `/api/v1/users/import`

根据模版批量导入用户，支持一次导入多条记录。

### 请求体
- 使用 `multipart/form-data` 提交文件字段 `file`，文件格式需为 `.xlsx`。

### Excel 模版字段
| 列序 | 标题     | 说明                                   |
| ---- | -------- | -------------------------------------- |
| A    | 用户名   | 必填，唯一标识，需与系统现有用户名不同 |
| B    | 密码     | 必填，至少 6 位                         |
| C    | 用户昵称 | 可选                                   |
| D    | 状态     | 可选，`normal` / `disabled` 或对应中文  |
| E    | 角色     | 可选，支持填写角色 ID、英文名或 role_key，多个以逗号分隔 |
| F    | 备注     | 可选                                   |

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "导入用户完成",
  "code": 200,
  "data": {
    "total": 2,
    "created": 2,
    "failed": []
  }
}
```
- `failed` 数组会返回每条失败记录的行号与错误原因，如：`[{"row": 5, "message": "用户名已存在"}]`。

### 异常响应
- `400` 模版不匹配、文件为空或参数错误。
- `401` 认证失败。

---

### 额外说明
- 系统使用状态码 `normal` / `disabled` 表示启用 / 停用，接口同时接受中文 `正常` / `停用` 作为输入。
- 用户被停用时会自动将 `is_active` 设为 `false`，无法再调用业务接口，需要重新启用后方可登录。
