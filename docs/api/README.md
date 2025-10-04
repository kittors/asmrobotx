# API 文档总览

本目录汇总项目已实现的 RESTful 接口，按照业务模块划分：

- [认证模块](auth.md)：注册、登录等与身份校验相关的接口。
- [用户模块](users.md)：获取当前用户信息。
- [组织模块](organizations.md)：查询可用组织列表。
- [访问控制模块](access_controls.md)：管理目录、菜单与按钮权限。
- [角色模块](roles.md)：角色管理、分配访问权限、导出列表。
- [系统字典模块](dictionaries.md)：提供图标、状态等枚举数据。

所有接口默认返回统一响应结构：

```json
{
  "msg": "操作描述",
  "data": { ... },
  "code": 200,
  "meta": {
    "access_token": "<可选，刷新后的令牌>"
  }
}
```

- `msg`：字符串，描述操作结果。
- `data`：业务数据，类型随接口定义变动，可为空。
- `code`：整数，等同于 HTTP 状态码或常见业务码。
- `meta.access_token`：在需要认证的接口中返回，表示刷新后的访问令牌，同步出现在响应头 `X-Access-Token` 中。

## 通用约定

- API 根路径：`/api/v1`
- 请求体：除特殊说明外，均使用 `application/json`。
- 身份认证：需要携带 JWT 的接口使用 `Authorization: Bearer <token>` 方式。
- 服务器错误：未预料异常统一返回 `500`，响应体 `msg` 为 `服务器内部错误`。

更多细节请参考各模块文档。
