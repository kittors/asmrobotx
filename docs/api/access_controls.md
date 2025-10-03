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
      "type": "menu",
      "icon": "icon-settings",
      "is_external": false,
      "permission_code": null,
      "route_path": null,
      "display_status": "show",
      "enabled_status": "enabled",
      "component_path": "layouts/SystemLayout.vue",
      "route_params": {
        "redirect": "/system/menu"
      },
      "keep_alive": true,
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
      "component_path": "views/system/menu/index.vue",
          "route_params": {
            "title": "菜单管理"
          },
          "keep_alive": false,
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

## GET `/api/v1/access-controls/routers`

返回前端动态路由所需的菜单配置，通常用于登录后拼装路由表。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取路由成功",
  "code": 200,
  "data": [
    {
      "name": "SystemMenu1",
      "path": "/system",
      "hidden": false,
      "component": "Layout",
      "redirect": "noRedirect",
      "meta": {
        "title": "系统管理",
        "icon": "system",
        "noCache": false,
        "link": null
      },
      "children": [
        {
          "name": "UserList2",
          "path": "user",
          "hidden": false,
          "component": "system/user/index",
          "meta": {
            "title": "用户管理",
            "icon": "user",
            "noCache": true,
            "link": null
          },
          "children": []
        }
      ]
    }
  ]
}
```

### 说明
- 仅返回启用状态的菜单节点，按钮与停用菜单会被自动过滤。
- `hidden` 字段由 `display_status` 推导，`noCache` 与 `keep_alive` 参数互为反义。
- 外链菜单会在 `meta.link` 返回 URL，前端可按需渲染。

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
    "component_path": "views/system/menu/index.vue",
    "route_params": {
      "title": "菜单管理"
    },
    "keep_alive": false,
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

创建新的访问控制项（菜单 / 按钮）。

### 请求体字段
- `parent_id` *(可选)*：父级节点 ID，根级菜单可省略或传 `null`。
- `name` *(必填)*：显示名称。
- `type` *(必填)*：`menu` 或 `button`，仅菜单可作为顶层节点。
- `icon` *(可选)*：图标标识，仅菜单使用。
- `is_external` *(可选)*：是否外链，仅菜单有效，默认为 `false`。
- `permission_code` *(可选，按钮必填)*：全局唯一的权限字符。按钮必须提供，菜单可留空。
- `route_path` *(可选，菜单使用)*：对应前端路由地址或外链 URL，未配置时可由前端自行处理跳转逻辑。
- `display_status` *(菜单必填)*：取值 `show` 或 `hidden`。
- `enabled_status` *(必填)*：取值 `enabled` 或 `disabled`。
- `sort_order` *(可选)*：排序字段，数字越小越靠前。
- `component_path` *(可选，菜单使用)*：前端组件路径，例如 `views/system/index.vue`。
- `route_params` *(可选)*：路由参数对象，默认为空对象。
- `keep_alive` *(可选)*：是否缓存菜单页面，默认为 `false`。

### 成功响应
- 状态码：`200`
- 响应体与详情接口一致。

### 异常响应
- `400` 参数校验失败，如菜单缺少必填字段、按钮设置外链等。
- `404` 指定父节点不存在。
- `409` `permission_code` 重复（在提交非空权限字符时可能发生）：`{"msg":"权限字符已存在","data":null,"code":409}`。

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
- 删除菜单前需先删除下级菜单及按钮。
- 删除按钮不会影响同级其他节点。
- 所有新增 / 修改 / 删除操作都会自动写入“操作日志”，便于在 `/api/v1/logs/operations` 页面审计。
