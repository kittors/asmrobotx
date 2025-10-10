# 文件列表分页方案（v1）

为解决 `/api/v1/files` 一次性全量返回导致的前端卡顿与大包传输问题，后端新增“分区分页”能力（目录分页 + 文件分页），并保持向后兼容：
- 不传分页参数时，仍然返回旧结构：`{ currentPath, items, rootPath? }`；
- 传入任意分页/排序参数时，返回分页结构：`{ currentPath, rootPath?, directories, files, items }`。

## 请求参数（新增）

- `limit`（int, 1–500，默认 50）：每页条目数
- `cursor`（string，可选）：分页游标（后端返回的不透明字符串）
- `include`（dirs|files|all，默认 all）：分页分区选择
- `orderBy`（name|size|time，默认 name）：排序字段（仅 `files` 分页有效）
- `order`（asc|desc，默认 asc）：排序方向（仅 `files` 分页有效）
- `countOnly`（bool，默认 false）：仅返回数量统计（不返回 items）

兼容参数：保留原有 `fileType`（image/document/spreadsheet/pdf/markdown/all）与 `search` 的过滤语义。

## 响应结构（分页模式）

```
{
  "code": 200,
  "msg": "获取文件列表成功",
  "data": {
    "currentPath": "/docs/",
    "rootPath": "/data/asmrobotx-files",
    "directories": {
      "items": [{ "name": "images", "type": "directory" }, { "name": "pdf" }],
      "nextCursor": "base64...", "hasMore": true
    },
    "files": {
      "items": [
        {
          "name": "a.jpg", "type": "file", "mimeType": "image/jpeg",
          "size": 102400, "lastModified": "2025-01-01T12:00:00Z",
          "previewUrl": "/api/v1/files/preview?storageId=1&path=/docs/a.jpg",
          "thumbnailUrl": "/api/v1/files/thumbnail?storageId=1&path=/docs/a.jpg&w=256"
        }
      ],
      "nextCursor": "base64...", "hasMore": false
    },
    "items": [ /* 兼容旧前端：directories.items + files.items */ ]
  }
}
```

- `directories`：仅返回当前目录“直接子目录”（不会返回深层目录）。
- `files`：仅返回当前目录下的文件。
- `items`：为兼容旧前端，将当前页的目录与文件简单拼接（目录在前，文件在后）。

> 旧结构（无分页参数）仍然返回 `{ currentPath, items, rootPath? }`，保证旧页面可用；新前端按分页参数接入后可获得更好的性能体验。

## 游标（Keyset）

- 后端使用 Keyset 方案生成 `cursor`，避免大偏移的性能劣化；
- `files`：基于排序字段（name/size/time）+ id 生成下一页游标；
- `directories`：基于目录路径（不区分大小写）+ id 生成下一页游标；
- 前端只需原样传回 `cursor`，不必解析。

## 计数（可选）

- `countOnly=true` 时返回：`{ counts: { dirCount, fileCount }, currentPath, rootPath? }`；
- 可用于页签/面包屑展示总数，正常浏览不必每次统计。

## 前端接入建议

- 列表加载
  - 初始：`GET /api/v1/files?storageId=&path=&limit=50&include=all`；
  - 触底加载：分别使用 `directories.nextCursor` 与 `files.nextCursor` 拉取更多；
  - 搜索/筛选：清空本地数据，带新参数从第一页拉取；
- 虚拟滚动 + 图片懒加载
  - 使用虚拟列表（表格/卡片）减少 DOM（如 vue-virtual-scroller/React Window）；
  - 图片 `<img loading="lazy">` 或 IntersectionObserver 懒加载；
- 排序
  - 切换 `orderBy/order` 时重置游标与本地列表，让后端统一排序；
- ETag/304（可选）
  - 可在请求时携带 `If-None-Match`，后端返回 304 时直接复用本地缓存。

## 注意事项

- 缩略图
  - 图片项自动返回 `thumbnailUrl`（默认 256px），首访懒生成，之后命中缓存；
  - 缓存位置：LOCAL → `/.thumbnails/...`；S3 → `thumbnails/...`；`/files/sync` 会忽略这些目录；
- 同步
  - 同步过程对异常与超长路径做了容错与跳过统计，不会因单个条目失败而中断；
- 兼容性
  - 无分页参数时仍返回旧结构，保证旧页面可用；新前端按分页参数接入后可获得更好的性能体验。

## 示例

- 拉第一页（目录 + 文件）
```
GET /api/v1/files?storageId=1&path=%2Fdocs%2F&limit=50&include=all
```
- 拉下一页文件
```
GET /api/v1/files?storageId=1&path=%2Fdocs%2F&limit=50&include=files&cursor=<files.nextCursor>
```
- 仅计数
```
GET /api/v1/files?storageId=1&path=%2Fdocs%2F&countOnly=true
```
