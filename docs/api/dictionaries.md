# 系统字典接口说明

字典接口用于为前端提供可配置的固定选项，例如图标、显示状态及启用状态。所有请求需携带 `Authorization: Bearer <access_token>`。

## GET `/api/v1/dictionaries/{type_code}`

按类型编码返回对应的字典项列表。

### 路径参数
- `type_code`：字典类型编码，例如 `icon_list`、`display_status`、`enable_status`。

### 成功响应
- 状态码：`200`
- 响应体示例：
```json
{
  "msg": "获取字典项成功",
  "data": [
    {
      "id": 1,
      "type_code": "display_status",
      "label": "显示",
      "value": "show",
      "description": null,
      "sort_order": 1
    },
    {
      "id": 2,
      "type_code": "display_status",
      "label": "隐藏",
      "value": "hidden",
      "description": null,
      "sort_order": 2
    }
  ],
  "code": 200
}
```

### 异常响应
- `401` 缺少或无效的认证信息。

### 备注
- 返回列表已按 `sort_order` 升序排序。
- 字典项支持后台扩展，前端只需根据 `value` 取值提交即可。
