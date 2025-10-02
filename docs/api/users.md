# 用户模块接口说明

## GET `/api/v1/users/me`

获取当前登录用户的完整信息，需要携带有效 JWT。

### 请求头
- `Authorization: Bearer <access_token>`

### 请求参数
- 无额外查询参数。

### 成功响应
- 状态码：`200`
- 响应体：
```json
{
  "msg": "获取用户信息成功",
  "data": {
    "user_id": 1,
    "username": "admin",
    "organization": {
      "org_id": 1,
      "org_name": "研发部"
    },
    "roles": ["admin"],
    "permissions": ["edit_self_profile", "manage_users", "view_dashboard"]
  },
  "code": 200
}
```

### 异常响应
- `401` 缺少或无效的令牌：
  - 缺少认证信息：`{"msg":"缺少认证信息","data":null,"code":401}`
  - Token 非 `bearer` 类型或解析失败。
- `403` 用户被标记为未激活：`{"msg":"用户未激活","data":null,"code":403}`

### 备注
- 权限列表为角色关联权限的去重集合，方便前端按需控制功能点。
- 若组织信息为空，`organization` 字段将返回 `null`。
