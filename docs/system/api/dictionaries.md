# 系统字典接口说明

系统字典模块为管理员提供字典类型与字典项的统一维护入口，可支持前端动态下拉框、状态枚举等通用配置。所有接口均需携带认证头：`Authorization: Bearer <access_token>`。

---

## 字典类型管理

### GET `/api/v1/dictionary_types`

获取全部字典类型列表，可按编码或显示名称进行模糊过滤。

- 查询参数：
  - `keyword`（可选）：匹配 `type_code` 或 `display_name`。

**成功响应示例**

```json
{
  "msg": "获取字典类型成功",
  "data": [
    {
      "id": 1,
      "type_code": "display_status",
      "display_name": "显示状态",
      "description": "用于控制前端组件展示与否",
      "sort_order": 1,
      "create_time": "2024-01-01 10:00:00",
      "update_time": "2024-01-01 10:00:00"
    }
  ],
  "code": 200
}
```

### POST `/api/v1/dictionary_types`

新增字典类型。

**请求体**

```json
{
  "type_code": "operation_scope",
  "display_name": "操作范围",
  "description": "划分不同操作的范围分类",
  "sort_order": 5
}
```

**成功响应**

```json
{
  "msg": "创建字典类型成功",
  "data": {
    "id": 8,
    "type_code": "operation_scope",
    "display_name": "操作范围",
    "description": "划分不同操作的范围分类",
    "sort_order": 5,
    "create_time": "2024-04-16 09:30:00",
    "update_time": "2024-04-16 09:30:00"
  },
  "code": 200
}
```

### PUT `/api/v1/dictionary_types/{type_code}`

更新指定字典类型的显示名称、描述或排序值。

**请求体**

```json
{
  "display_name": "操作范围（更新后）",
  "description": "更新后的说明",
  "sort_order": 3
}
```

**成功响应**

```json
{
  "msg": "更新字典类型成功",
  "data": {
    "id": 8,
    "type_code": "operation_scope",
    "display_name": "操作范围（更新后）",
    "description": "更新后的说明",
    "sort_order": 3,
    "create_time": "2024-04-16 09:30:00",
    "update_time": "2024-04-16 09:42:00"
  },
  "code": 200
}
```

### DELETE `/api/v1/dictionary_types/{type_code}`

软删除字典类型，并同步软删除其下所有字典项。

**成功响应**

```json
{
  "msg": "删除字典类型成功",
  "data": {
    "type_code": "operation_scope",
    "deleted_items": 4
  },
  "code": 200
}
```

- 若类型不存在或已删除，返回 `404`。

---

## 字典项管理

### GET `/api/v1/dictionaries/{type_code}`

查询指定类型下的字典项，支持分页或一次性获取全部。

- 路径参数：
  - `type_code`：字典类型编码。
- 查询参数：
  - `page`（默认 `1`）：页码。
  - `size`（默认 `10`）：每页条数，最大 200；当 `all=true` 时忽略。
  - `keyword`（可选）：按 `label` 或 `value` 模糊搜索。
  - `all`（可选，默认 `false`）：为 `true` 时一次性返回全部数据（仍返回分页结构，`page=1`，`size=total`）。

**成功响应**

```json
{
  "msg": "获取字典项成功",
  "data": {
    "total": 12,
    "page": 1,
    "size": 10,
    "list": [
      {
        "id": 101,
        "type_code": "display_status",
        "label": "显示",
        "value": "show",
        "description": "用于表示菜单展示",
        "sort_order": 1,
        "create_time": "2024-04-01 08:00:00",
        "update_time": "2024-04-01 08:00:00"
      }
    ]
  },
  "code": 200
}
```

### POST `/api/v1/dictionaries`

在指定类型下新增字典项。

**请求体**

```json
{
  "type_code": "display_status",
  "label": "草稿",
  "value": "draft",
  "description": "仅保存，不对外展示",
  "sort_order": 5
}
```

**成功响应**

```json
{
  "msg": "创建字典项成功",
  "data": {
    "id": 204,
    "type_code": "display_status",
    "label": "草稿",
    "value": "draft",
    "description": "仅保存，不对外展示",
    "sort_order": 5,
    "create_time": "2024-04-16 10:15:00",
    "update_time": "2024-04-16 10:15:00"
  },
  "code": 200
}
```

- 若 `type_code` 不存在或 `value` 冲突，将分别返回 `404` 与 `409`。

### PUT `/api/v1/dictionaries/{id}`

更新字典项的显示文本、值、描述、排序。

```json
{
  "label": "草稿（更新）",
  "value": "draft",
  "description": "说明已更新",
  "sort_order": 7
}
```

**成功响应**

```json
{
  "msg": "更新字典项成功",
  "data": {
    "id": 204,
    "type_code": "display_status",
    "label": "草稿（更新）",
    "value": "draft",
    "description": "说明已更新",
    "sort_order": 7,
    "create_time": "2024-04-16 10:15:00",
    "update_time": "2024-04-16 10:20:00"
  },
  "code": 200
}
```

### DELETE `/api/v1/dictionaries/{id}`

软删除指定字典项。

**成功响应**

```json
{
  "msg": "删除字典项成功",
  "data": {
    "id": 204
  },
  "code": 200
}
```

- 字典项不存在时返回 `404`。
