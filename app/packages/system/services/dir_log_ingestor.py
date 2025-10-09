"""本地目录操作记录文件导入器。

读取每个 LOCAL 存储根目录下的 .dir_ops.jsonl 并将记录导入数据库。
记录格式（JSON Lines，每行一个 JSON 对象）：
{
  "action": "create|rename|move|delete|copy",
  "path_old": "/foo/",
  "path_new": "/bar/",
  "operate_time": "2025-01-01T10:00:00Z"
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.packages.system.core.logger import logger
from app.packages.system.crud.storage_config import storage_config_crud
from app.packages.system.crud.directory_change_record import directory_change_record_crud


def _parse_iso(s: str) -> datetime:
    try:
        # Python 3.11: fromisoformat 支持带 Z 的形式需替换
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


def ingest_local_dir_logs(db: Session) -> int:
    """导入所有 LOCAL 存储的目录变更记录，返回成功插入的条数。

    幂等：借助数据库唯一索引避免重复插入。
    """
    count = 0
    configs = storage_config_crud.list_all(db)
    for cfg in configs:
        try:
            if (cfg.type or "").upper() != "LOCAL" or not cfg.local_root_path:
                continue
            record_path = Path(cfg.local_root_path).resolve() / ".dir_ops.jsonl"
            if not record_path.exists():
                continue
            with open(record_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        action = str(obj.get("action") or "").strip()
                        if not action:
                            continue
                        path_old: Optional[str] = obj.get("path_old")
                        path_new: Optional[str] = obj.get("path_new")
                        ts_raw = str(obj.get("operate_time") or "")
                        operate_time = _parse_iso(ts_raw)
                        # 插入（唯一索引防重）
                        directory_change_record_crud.create(
                            db,
                            {
                                "storage_id": cfg.id,
                                "action": action,
                                "path_old": path_old,
                                "path_new": path_new,
                                "operate_time": operate_time,
                            },
                        )
                        count += 1
                    except Exception:
                        logger.debug("Skip invalid dir ops line in %s", record_path)
        except Exception:
            logger.warning("Failed to ingest dir ops for storage %s", getattr(cfg, "name", cfg.id), exc_info=True)
    return count
