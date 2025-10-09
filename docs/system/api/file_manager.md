# 文件管理系统 API（v1）

接口前缀：`/api/v1`（均需要认证：`Authorization: Bearer <token>`）

## 存储源管理

### GET /storage-configs
列出所有存储源配置。

响应示例：
```json
{
  "msg": "获取存储源配置成功",
  "code": 200,
  "data": [
    {
      "id": 1,
      "name": "本地存储 (默认)",
      "type": "LOCAL",
      "local_root_path": "/tmp/asmrobotx-files",
      "status": "connected",
      "created_at": "2025-01-01T10:00:00Z"
    }
  ]
}
```

### GET /storage-configs/{id}
获取单个存储源配置详情。

响应示例：
```json
{
  "msg": "获取存储源详情成功",
  "code": 200,
  "data": {
    "id": 1,
    "name": "本地存储 (默认)",
    "type": "LOCAL",
    "local_root_path": "/tmp/asmrobotx-files",
    "status": "connected",
    "created_at": "2025-01-01T10:00:00Z"
  }
}
```

### POST /storage-configs
新增存储源。

- LOCAL 示例：
```json
{
  "name": "开发机文件",
  "type": "LOCAL",
  "local_root_path": "/tmp/dev-files"
}
```

- S3 示例（标准 AWS 或兼容 S3，如 MinIO、七牛、阿里云等）：
```json
{
  "name": "项目数据 (S3)",
  "type": "S3",
  "region": "ap-east-1",
  "bucket_name": "my-bucket",
  "access_key_id": "AKIA...",
  "secret_access_key": "***",
  "path_prefix": "/project/",
  "config_key": "proj_s3",
  "endpoint_url": "https://minio.example.com",
  "custom_domain": "cdn.example.com",
  "use_https": true,
  "acl_type": "public"
}
```

字段说明（S3）：
- `config_key`：配置唯一 key，便于引用（可选但建议设置）。
- `endpoint_url`：S3 兼容端点（如 MinIO 地址）；留空则使用默认 AWS 端点。可仅填主机名（如 `minio.example.com`），系统会按 `use_https` 自动补全协议。
- `custom_domain`：自定义访问域名/CDN 域名（可选）。
- `use_https`：直链拼接是否使用 https，默认 `true`。
- `acl_type`：桶权限类型，`private`（预签名跳转，默认）、`public`/`custom`（直链访问）。

### PUT /storage-configs/{id}
更新存储源（可部分字段）。

### DELETE /storage-configs/{id}
删除存储源配置（仅删除配置，不动真实存储）。

### POST /storage-configs/test
测试连通性（不保存配置）。

请求体同 POST /storage-configs。

响应：`{"success": true|false}`（在 `data` 下）。当 `acl_type=public/custom` 且提供了 `custom_domain` 时，下载/预览接口会返回直链重定向；当 `acl_type=private` 时，返回预签名 URL 重定向。

---

## 文件与文件夹

所有接口需 `storageId` 指定存储源。

### GET /files
列出目录内容。

查询：`storageId`, `path=/`, `fileType=image|document|spreadsheet|pdf|markdown|all`, `search`

- 当提供 `fileType` 且不为 `all` 时：仅返回匹配类型的“文件”，目录将被隐藏；
- 当未提供或为 `all`：返回当前目录下的目录与所有文件。
- 内部文件：对于 LOCAL 存储，系统在根目录维护的记录文件 `.dir_ops.jsonl` 为内部用途，不会出现在列表结果中。

返回字段说明：
- `currentPath`：当前浏览的相对目录路径（统一以 `/` 开头并以 `/` 结尾，例如 `/`、`/docs/`）。
- `rootPath`：当存储类型为 LOCAL 时，返回该存储源的根目录绝对路径（例如 `/tmp/asmrobotx-files`）；S3 场景不返回该字段。

响应：
```json
{
  "msg": "获取文件列表成功",
  "code": 200,
  "data": {
    "currentPath": "/docs/",
    "rootPath": "/tmp/asmrobotx-files",
    "items": [
      {
        "name": "a.txt",
        "type": "file",
        "mimeType": "text/plain",
        "size": 11,
        "lastModified": "2025-01-01T12:00:00Z",
        "previewUrl": "/api/v1/files/preview?storageId=1&path=/docs/a.txt"
      },
      { "name": "images", "type": "directory", "size": 0 }
    ]
  }
}
```

### POST /files
上传文件（`multipart/form-data`）。

查询：`storageId`, `path=/`, `purpose=general`

- 支持多文件上传；
- 当同名文件已存在时，自动为新文件生成别名：如 `a.png` → `a(1).png`、`a(2).png`；
- 返回数组项包含：
  - `name`: 原始文件名；
  - `stored_name`: 实际存储的文件名（可能为别名）；
  - `status`/`message`；
  成功项会在数据库 `file_records` 表中写入一条记录（含 `original_name`、`alias_name`、`purpose` 等）。

字段：`files`（可多文件）。

响应：文件结果数组（每个 `name/stored_name/status/message`）。

### GET /files/download
下载文件（LOCAL：直接流；S3：当 `acl_type=private` 返回预签名 URL 重定向，`public/custom` 返回直链重定向）。

### GET /files/preview
预览文件（LOCAL：内联流；S3：当 `acl_type=private` 返回预签名 URL 重定向，`public/custom` 返回直链重定向）。

### POST /folders
创建文件夹。

查询：`storageId`, `path`（父目录）；请求体：`{"name": "Docs"}`。

- 若父目录下已存在同名文件夹，将自动使用别名：`Docs(1)`、`Docs(2)` ...，并返回最终 `folder_name`。

### PATCH /files
重命名（文件/文件夹）。

体：`{"oldPath":"/docs/a.txt","newPath":"/docs/a1.txt"}`。

### POST /files/move
移动（不跨存储源）。

体：`{"sourcePaths":["/docs/a1.txt"],"destinationPath":"/archive"}`。

### POST /files/copy
复制（不跨存储源）。

体同上。

### DELETE /files
删除（文件/文件夹可混合）。

体：`{"paths":["/docs/a1.txt","/archive"]}`。

---

## 复制/粘贴/剪切（剪贴板）

为方便前端“复制后到目标目录粘贴”、“剪切后粘贴移动”的交互，提供服务端剪贴板接口。

说明：不支持跨存储源（剪贴板记录了来源 storageId，粘贴时需一致）。

### POST /files/clipboard
设置剪贴板。

查询：`storageId`

请求体：
```json
{ "action": "copy", "paths": ["/docs/a.txt", "/docs/b"] }
```
- `action`: `copy`（复制）或 `cut`（剪切/移动）
- `paths`: 待复制/剪切的相对路径数组

响应：返回当前剪贴板内容。

### GET /files/clipboard
获取当前剪贴板内容。

响应：
```json
{
  "msg": "获取剪贴板成功",
  "code": 200,
  "data": { "action": "copy", "storage_id": 1, "paths": ["/docs/a.txt"], "ts": "..." }
}
```

### DELETE /files/clipboard
清空剪贴板。

### POST /files/paste
在目标目录执行粘贴。

查询：`storageId`, `destinationPath`, `clearAfter=true`

行为：
- 若剪贴板 `action` 为 `copy`：对 `paths` 执行复制到 `destinationPath`；
- 若为 `cut`：对 `paths` 执行移动到 `destinationPath`；
- 默认粘贴后清空剪贴板（可用 `clearAfter=false` 禁用）。

---

## 环境变量（本地存储）

- `LOCAL_FILE_ROOT`：可选。若设置且系统首次启动时没有任何存储源配置，会自动创建一个默认的 LOCAL 存储源，根目录即该变量值。
  - 开发示例：`LOCAL_FILE_ROOT=/tmp/asmrobotx-files`
  - 生产示例：`LOCAL_FILE_ROOT=/data/asmrobotx-files`（建议挂载持久卷）

> 提示：S3 功能需后端安装 `boto3`（已在 requirements.txt 中）。

---

## 文件记录（数据库）

上传成功后，系统会在数据库表 `file_records` 记录一条元数据，用于追踪文件原名/别名及用途。

- 表：`file_records`
- 关键字段：
  - `storage_id`: 存储源 ID
  - `directory`: 所在目录（以 `/` 开头，末尾不含文件名）
  - `original_name`: 上传时的原始文件名
  - `alias_name`: 实际存储使用的文件名（若重名则为 `name(1).ext` 这类别名）
  - `purpose`: 上传目的，默认 `general`
  - `size_bytes`: 文件大小（字节）
  - `mime_type`: 服务器推断的 MIME 类型
  - `create_time`: 创建时间

说明：目前该表仅用于后台追踪记录；如需对该表提供查询 API（按目录、按用途检索等），可按需补充接口。

---

## 目录操作记录与导入（LOCAL 存储）

当存储源为本地目录（LOCAL）时，系统会在该存储根目录下生成一个“记录文件”，用于记录目录层面的新增/重命名/移动/删除/复制操作。应用启动时会自动读取这些记录并导入数据库。

- 记录文件位置：`<local_root_path>/.dir_ops.jsonl`
- 文件格式：JSON Lines（每行一个 JSON 对象）

示例内容：
```json
{"action":"create","path_new":"/reports/","operate_time":"2025-01-01T10:00:00Z"}
{"action":"rename","path_old":"/old/","path_new":"/new/","operate_time":"2025-01-01T10:01:00Z"}
{"action":"move","path_old":"/a/","path_new":"/b/a/","operate_time":"2025-01-01T10:02:00Z"}
{"action":"delete","path_old":"/tmp/","operate_time":"2025-01-01T10:03:00Z"}
{"action":"copy","path_old":"/tpl/","path_new":"/tpl-copy/","operate_time":"2025-01-01T10:04:00Z"}
```

- 导入时机：应用 `startup`（例如你在开发环境执行：
  `docker compose --env-file .env.development down -v && docker compose --env-file .env.development up -d db redis && uvicorn app.main:app --reload`），
  启动后会扫描所有 LOCAL 存储的该文件并导入。
- 导入表：`directory_change_records`
  - 字段：`storage_id`, `action`, `path_old`, `path_new`, `operate_time`, `create_time` 等
  - 幂等：通过唯一索引避免重复导入（`storage_id + action + path_old + path_new + operate_time`）
- 注意：导入后记录文件不会清空；重复启动不会产生重复记录。
