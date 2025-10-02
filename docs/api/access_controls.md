# 访问控制模块接口说明

所有接口均需在请求头携带 `Authorization: Bearer <access_token>`，用于校验当前用户身份。

## GET `/api/v1/access-controls`

获取访问控制项的树形结构，可按名称与启用状态筛选。

### 查询参数
- `name` *(可选)*：模糊匹配访问控制项名称。
- `enabled_status` *(可选)*：过滤启用状态，值为 `enabled`、`disabled` 或 `all`（默认忽略过滤）。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取访问控制列表成功",
  "data": [
    {
      "id": 1,
      "parent_id": null,
      "name": "系统管理",
      "type": "directory",
      "icon": "icon-settings",
      "is_external": false,
      "permission_code": "system:manage",
      "route_path": "/system",
      "display_status": "show",
      "enabled_status": "enabled",
      "effective_display_status": "show",
      "effective_enabled_status": "enabled",
      "sort_order": 1,
      "children": [
        {
          "id": 2,
          "parent_id": 1,
          "name": "菜单管理",
          "type": "menu",
          "icon": "icon-dashboard",
          "is_external": false,
          "permission_code": "system:menu:list",
          "route_path": "/system/menu",
          "display_status": "show",
          "enabled_status": "disabled",
          "effective_display_status": "show",
          "effective_enabled_status": "disabled",
          "sort_order": 2,
          "children": []
        }
      ]
    }
  ],
  "code": 200
}
```

### 异常响应
- `401` 缺少或无效令牌。

### 备注
- 当父节点被停用或隐藏时，其子节点的 `effective_enabled_status` 与 `effective_display_status` 会同步继承父级的停用/隐藏状态。

---

## GET `/api/v1/access-controls/{item_id}`

获取单个访问控制项的详细信息，常用于编辑前加载表单。

### 路径参数
- `item_id`：访问控制项 ID。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取访问控制项详情成功",
  "data": {
    "id": 2,
    "parent_id": 1,
    "name": "菜单管理",
    "type": "menu",
    "icon": "icon-dashboard",
    "is_external": false,
    "permission_code": "system:menu:list",
    "route_path": "/system/menu",
    "display_status": "show",
    "enabled_status": "disabled",
    "sort_order": 2,
    "create_time": "2024-01-01T12:00:00+00:00",
    "update_time": "2024-01-01T12:30:00+00:00"
  },
  "code": 200
}
```

### 异常响应
- `401` 认证失败。
- `404` 目标项不存在：`{"msg":"访问控制项不存在","data":null,"code":404}`。

---

## POST `/api/v1/access-controls`

创建新的访问控制项（目录 / 菜单 / 按钮）。

### 请求体字段
- `parent_id` *(可选)*：父级节点 ID，根目录可省略或传 `null`。
- `name` *(必填)*：显示名称。
- `type` *(必填)*：`directory`、`menu` 或 `button`。
- `icon` *(可选)*：图标标识，仅目录/菜单使用。
- `is_external` *(可选)*：是否外链，目录/菜单有效，默认为 `false`。
- `permission_code` *(必填)*：全局唯一的权限字符。
- `route_path` *(目录/菜单必填)*：对应前端路由地址或外链 URL。
- `display_status` *(目录/菜单必填)*：取值 `show` 或 `hidden`。
- `enabled_status` *(必填)*：取值 `enabled` 或 `disabled`。
- `sort_order` *(可选)*：排序字段，数字越小越靠前。

### 成功响应
- 状态码：`200`
- 响应体与详情接口一致。

### 异常响应
- `400` 参数校验失败，如目录缺少路由地址、按钮设置外链等。
- `404` 指定父节点不存在。
- `409` `permission_code` 重复：`{"msg":"权限字符已存在","data":null,"code":409}`。

---

## PUT `/api/v1/access-controls/{item_id}`

更新访问控制项，类型与父级不可变更。

### 请求体字段
- 同创建接口，`type` 与 `parent_id` 不可提交。

### 成功响应
- 状态码：`200`
- 响应体与详情接口一致。

### 异常响应
- 同创建接口，其中 `404` 表示目标项不存在。

---

## PATCH `/api/v1/access-controls/{item_id}/reorder`

拖拽调整访问控制项的层级与同级排序。

### 请求体字段
- `target_parent_id` *(可选)*：目标父级 ID，设置为 `null` 表示移动到顶层（仅目录类型可用）。
- `target_index` *(必填)*：插入到目标父级下的排序位置（从 `0` 开始）。

### 成功响应
- 状态码：`200`
- 响应体：
```json
{
  "msg": "更新排序成功",
  "data": {
    "id": 5,
    "parent_id": 2,
    "name": "菜单A2",
    "type": "menu",
    "icon": null,
    "is_external": false,
    "permission_code": "system:menu:a2",
    "route_path": "/system/menu/a2",
    "display_status": "show",
    "enabled_status": "enabled",
    "sort_order": 0,
    "create_time": "2024-01-01T12:00:00+00:00",
    "update_time": "2024-01-01T12:35:00+00:00"
  },
  "code": 200
}
```

### 异常响应
- `400` 非法操作：如尝试将目录移动到非顶层、将节点拖拽到自身或子节点、或将子项放置到按钮节点下。
- `404` 目标节点或父节点不存在。

### 备注
- 移动成功后，同级节点的 `sort_order` 会重新按 0,1,2 顺序编号。
- 当前节点的 `parent_id` 将更新为目标父级的 ID。

---

## DELETE `/api/v1/access-controls/{item_id}`

删除访问控制项，采用软删除策略。

### 成功响应
- 状态码：`200`
- 响应体：`{"msg":"删除访问控制项成功","data":null,"code":200}`。

### 异常响应
- `400` 仍存在子节点：`{"msg":"该项包含子项，无法删除","data":null,"code":400}`。
- `401` 认证失败。
- `404` 目标项不存在。

### 备注
- 删除目录或菜单前需先删除下级菜单及按钮。
- 删除按钮不会影响同级其他节点。
