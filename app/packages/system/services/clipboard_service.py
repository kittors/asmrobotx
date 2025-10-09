"""简单的服务端剪贴板：用于文件复制/剪切后延迟粘贴。

优先使用 Redis（通过环境变量 REDIS_HOST/REDIS_PORT/REDIS_DB），不可用时回退到进程内存。
结构：{"action":"copy|cut","storage_id":1,"paths":["/a.txt"],"ts":"ISO"}
键：clipboard:{user_id}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.packages.system.core.config import get_settings
from app.packages.system.core.logger import logger


class _InMemoryClipboard:
    def __init__(self) -> None:
        self._store: dict[int, str] = {}

    def set(self, user_id: int, payload: dict[str, Any]) -> None:
        self._store[user_id] = json.dumps(payload, ensure_ascii=False)

    def get(self, user_id: int) -> Optional[dict[str, Any]]:
        raw = self._store.get(user_id)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def clear(self, user_id: int) -> None:
        self._store.pop(user_id, None)


class _RedisClipboard:
    def __init__(self, url: str):
        import redis  # type: ignore

        self._client = redis.Redis.from_url(url, decode_responses=True)
        try:
            self._client.ping()
        except Exception as exc:
            raise RuntimeError(f"Redis not available: {exc}")

    def _key(self, user_id: int) -> str:
        return f"clipboard:{user_id}"

    def set(self, user_id: int, payload: dict[str, Any]) -> None:
        self._client.set(self._key(user_id), json.dumps(payload, ensure_ascii=False), ex=24 * 3600)

    def get(self, user_id: int) -> Optional[dict[str, Any]]:
        raw = self._client.get(self._key(user_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def clear(self, user_id: int) -> None:
        self._client.delete(self._key(user_id))


class ClipboardService:
    def __init__(self) -> None:
        settings = get_settings()
        try:
            self._backend = _RedisClipboard(settings.redis_url)
            logger.info("Clipboard service using Redis: %s", settings.redis_url)
        except Exception:
            self._backend = _InMemoryClipboard()
            logger.warning("Clipboard service falling back to in-memory store")

    def set(self, user_id: int, *, action: str, storage_id: int, paths: list[str]) -> dict[str, Any]:
        payload = {
            "action": action,
            "storage_id": storage_id,
            "paths": list(paths or []),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._backend.set(user_id, payload)
        return payload

    def get(self, user_id: int) -> Optional[dict[str, Any]]:
        return self._backend.get(user_id)

    def clear(self, user_id: int) -> None:
        self._backend.clear(user_id)


clipboard_service = ClipboardService()

