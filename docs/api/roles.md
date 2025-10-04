# 角色管理模块接口说明

所有接口需携带 `Authorization: Bearer <access_token>` 头部，通过后端校验当前会话身份。

## GET `/api/v1/roles`

分页查询角色列表，支持关键字与状态过滤。

### 查询参数
- `name` *(可选)*：角色名称模糊匹配。
- `role_key` *(可选)*：权限字符模糊匹配。
- `statuses` *(可选)*：角色状态数组，支持传入英文代码 `normal` / `disabled` 或中文 `正常` / `停用`。
- `start_time` *(可选)*：创建时间开始，格式 `YYYY-MM-DD HH:MM:SS`。
- `end_time` *(可选)*：创建时间结束，格式 `YYYY-MM-DD HH:MM:SS`。
- `page` *(可选)*：页码，从 `1` 开始，默认 `1`。
- `page_size` *(可选)*：每页数量，默认 `20`，上限 `200`。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取角色列表成功",
  "code": 200,
  "data": {
    "total": 1,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "role_id": 1,
        "role_name": "管理员",
        "role_key": "admin",
        "sort_order": 1,
        "status": "normal",
        "status_label": "正常",
        "remark": "系统预置角色",
        "create_time": "2024-02-01 09:00:00"
      }
    ]
  }
}
```

### 异常响应
- `400` 请求参数格式错误。
- `401` 未携带或携带无效的访问令牌。

---

## GET `/api/v1/roles/{role_id}`

根据角色 ID 获取详细信息，可用于编辑前回显。

### 路径参数
- `role_id`：角色主键 ID。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取角色详情成功",
  "code": 200,
  "data": {
    "role_id": 1,
    "role_name": "管理员",
    "role_key": "admin",
    "sort_order": 1,
    "status": "normal",
    "status_label": "正常",
    "remark": "系统预置角色",
    "create_time": "2024-02-01 09:00:00",
    "update_time": "2024-02-01 09:30:00",
    "permission_ids": [10, 11, 12],
    "permission_codes": [
      "system:role:list",
      "system:role:add",
      "system:role:edit"
    ]
  }
}
```

### 异常响应
- `401` 认证失败。
- `404` 角色不存在或已被删除。

---

## POST `/api/v1/roles`

新增角色，并关联访问权限（访问控制树中的节点）。

### 请求体字段
- `name` *(必填)*：角色名称，需唯一。
- `role_key` *(必填)*：权限字符，同样需唯一。
- `sort_order` *(可选)*：显示顺序，默认 `0`，数值越小越靠前。
- `status` *(可选)*：角色状态，默认为 `normal`（正常），可选 `disabled`（停用）。
- `permission_ids` *(可选)*：访问权限 ID 列表，对应访问控制节点 ID，父子联动由前端控制。
- `remark` *(可选)*：备注，留空表示无备注。

### 成功响应
- 状态码：`200`
- 响应体同详情接口。

### 异常响应
- `400` 参数校验失败，如权限 ID 无效。
- `401` 认证失败。
- `409` 角色名称或权限字符重复。

---

## PUT `/api/v1/roles/{role_id}`

更新既有角色信息及权限关联。

### 请求体字段
与新增接口一致。

### 成功响应
- 状态码：`200`
- 响应体同详情接口。

### 异常响应
- `400` 参数校验失败。
- `401` 认证失败。
- `404` 角色不存在。
- `409` 角色名称或权限字符重复。

---

## PATCH `/api/v1/roles/{role_id}/status`

快速切换角色状态（正常 / 停用）。

### 请求体字段
- `status` *(必填)*：`normal` 或 `disabled`，也接受中文 `正常` / `停用`。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "更新角色状态成功",
  "code": 200,
  "data": {
    "role_id": 1,
    "role_name": "管理员",
    "role_key": "admin",
    "sort_order": 1,
    "status": "disabled",
    "status_label": "停用",
    "remark": "系统预置角色",
    "create_time": "2024-02-01 09:00:00"
  }
}
```

### 异常响应
- `400` 状态值非法。
- `401` 认证失败。
- `404` 角色不存在。

---

## DELETE `/api/v1/roles/{role_id}`

删除角色（软删除）。内置角色或仍绑定用户的角色不可删除。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "删除角色成功",
  "code": 200,
  "data": {
    "role_id": 8
  }
}
```

### 异常响应
- `400` 角色仍有关联用户，无法删除。
- `401` 认证失败。
- `403` 内置角色（如 `admin` / `user`）禁止删除。
- `404` 角色不存在。

---

## GET `/api/v1/roles/export`

按条件导出角色列表为 Excel (`.xlsx`) 文件，字段包括角色名称、权限字符、显示顺序、状态、创建时间。

### 查询参数
与列表接口一致。

### 成功响应
- 状态码：`200`
- 响应头：`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- 响应体：Excel 二进制流，文件名形如 `roles-20240201120000.xlsx`。

### 异常响应
- `400` 请求参数格式错误。
- `401` 认证失败。

---

## 其他说明

- `permission_ids` 来源于访问控制树，可先调用访问控制模块获取树形数据后，让前端进行父子联动选择。
- 所有时间字段默认返回本地时区的 `YYYY-MM-DD HH:MM:SS` 字符串。
- 角色删除采用软删除机制，历史记录仍保留在数据库中，仅在查询时被过滤。
