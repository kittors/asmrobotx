# 认证模块接口说明

## POST `/api/v1/auth/register`

用户注册，默认分配普通用户角色。注册不再允许选择组织，后端自动归属默认组织。

### 请求头
- `Content-Type: application/json`

### 请求体
```json
{
  "username": "string (3~50 位)",
  "password": "string (6~128 位)"
}
```

### 成功响应
- 状态码：`200`
- 响应体：
```json
{
  "msg": "注册成功",
  "data": {
    "user_id": 2,
    "username": "tester",
    "organization": {
      "org_id": 1,
      "org_name": "研发部"
    },
    "roles": ["user"]
  },
  "code": 200
}
```

### 异常响应
- `409` 用户名已存在：`{"msg":"用户名已存在","data":null,"code":409}`
- `404` 默认组织不存在：`{"msg":"默认组织不存在","data":null,"code":404}`
- `422` 请求体验证失败（字段缺失/格式错误）。

---

## POST `/api/v1/auth/login`

用户登录并获取访问令牌。

### 请求头
- `Content-Type: application/json`

### 请求体
```json
{
  "username": "admin",
  "password": "admin123"
}
```

### 成功响应
- 状态码：`200`
- 响应体：
```json
{
  "msg": "登录成功",
  "data": {
    "access_token": "<JWT Token>",
    "token_type": "bearer"
  },
  "code": 200,
  "meta": {
    "access_token": "<最新 JWT Token>"
  }
}
```

### 异常响应
- `401` 用户名或密码错误：`{"msg":"用户名或密码错误","data":null,"code":401}`
- `422` 请求体验证失败。

### 备注
- 令牌的基础有效期由环境变量 `ACCESS_TOKEN_EXPIRE_MINUTES` 控制（默认 60 分钟），后端会在 Redis（或内存回退）中维护滑动会话，只要在该时间窗口内持续调用受保护接口，会话就会自动续期，无需替换本地 Token。
- 若在指定时间内无任何请求，会话将失效，后续请求会返回 `401` 需重新登录。
- 所有需要认证的接口均要求在请求头携带 `Authorization: Bearer <access_token>`。

---

## POST `/api/v1/auth/logout`

退出登录接口，用于在客户端侧清除现有的访问令牌。后端不维护会话状态，调用成功即表示当前令牌不再被推荐使用。

### 请求头
- `Authorization: Bearer <access_token>`

### 请求体
- 无需请求体。

### 成功响应
- 状态码：`200`
- 响应体：
```json
{
  "msg": "退出登录成功",
  "data": null,
  "code": 200
}
```

### 异常响应
- `401` 缺少或无效的令牌：`{"msg":"缺少认证信息","data":null,"code":401}` 等。

### 备注
- 由于系统采用 JWT 无状态认证，后端不会主动失效历史令牌。请调用方在收到成功响应后立即删除本地缓存的 `access_token`。
