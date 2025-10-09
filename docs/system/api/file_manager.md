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
      "localRootPath": "/tmp/asmrobotx-files",
      "status": "connected",
      "createdAt": "2025-01-01T10:00:00Z"
    }
  ]
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

- S3 示例：
```json
{
  "name": "项目数据 (S3)",
  "type": "S3",
  "region": "ap-east-1",
  "bucket_name": "my-bucket",
  "access_key_id": "AKIA...",
  "secret_access_key": "***",
  "path_prefix": "/project/"
}
```

### PUT /storage-configs/{id}
更新存储源（可部分字段）。

### DELETE /storage-configs/{id}
删除存储源配置（仅删除配置，不动真实存储）。

### POST /storage-configs/test
测试连通性（不保存配置）。

请求体同 POST /storage-configs。

响应：`{"success": true|false}`（在 `data` 下）。

---

## 文件与文件夹

所有接口需 `storageId` 指定存储源。

### GET /files
列出目录内容。

查询：`storageId`, `path=/`, `fileType=image|document|spreadsheet|pdf|markdown|all`, `search`

响应：
```json
{
  "msg": "获取文件列表成功",
  "code": 200,
  "data": {
    "currentPath": "/docs/",
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

查询：`storageId`, `path=/`

字段：`files`（可多文件）。

响应：文件结果数组（每个 `name/status/message`）。

### GET /files/download
下载文件（LOCAL：直接流；S3：重定向预签名 URL）。

### GET /files/preview
预览文件（LOCAL：内联流；S3：重定向预签名 URL）。

### POST /folders
创建文件夹。

查询：`storageId`, `path`（父目录）；请求体：`{"name": "Docs"}`。

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

## 环境变量（本地存储）

- `LOCAL_FILE_ROOT`：可选。若设置且系统首次启动时没有任何存储源配置，会自动创建一个默认的 LOCAL 存储源，根目录即该变量值。
  - 开发示例：`LOCAL_FILE_ROOT=/tmp/asmrobotx-files`
  - 生产示例：`LOCAL_FILE_ROOT=/data/asmrobotx-files`（建议挂载持久卷）

> 提示：S3 功能需后端安装 `boto3`（已在 requirements.txt 中）。

