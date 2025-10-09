"""会话管理：使用 Redis 或内存后端实现滑动过期的访问会话。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis

from app.packages.system.core.config import get_settings
from app.packages.system.core.logger import logger


class SessionBackend:
    """会话后端基类，定义滑动过期操作的接口。"""

    def create_session(self, user_id: int, ttl_seconds: int) -> str:  # pragma: no cover - interface definition
        raise NotImplementedError

    def touch_session(self, session_id: str, user_id: int, ttl_seconds: int) -> bool:  # pragma: no cover
        raise NotImplementedError

    def delete_session(self, session_id: str) -> None:  # pragma: no cover
        raise NotImplementedError


class RedisSessionBackend(SessionBackend):
    """基于 Redis 的会话后端，实现会话 TTL 的持久化伸缩。"""

    def __init__(self, url: str) -> None:
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._client.ping()

    def create_session(self, user_id: int, ttl_seconds: int) -> str:
        session_id = uuid.uuid4().hex
        key = self._build_key(session_id)
        self._client.hset(key, mapping={"user_id": str(user_id)})
        self._client.expire(key, ttl_seconds)
        return session_id

    def touch_session(self, session_id: str, user_id: int, ttl_seconds: int) -> bool:
        key = self._build_key(session_id)
        stored_user_id = self._client.hget(key, "user_id")
        if stored_user_id is None or stored_user_id != str(user_id):
            return False
        self._client.expire(key, ttl_seconds)
        return True

    def delete_session(self, session_id: str) -> None:
        key = self._build_key(session_id)
        self._client.delete(key)

    @staticmethod
    def _build_key(session_id: str) -> str:
        return f"session:{session_id}"


class InMemorySessionBackend(SessionBackend):
    """内存后端用于测试或缺少 Redis 时的回退实现。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[int, datetime]] = {}
        self._lock = threading.Lock()

    def create_session(self, user_id: int, ttl_seconds: int) -> str:
        session_id = uuid.uuid4().hex
        expires_at = self._expiry(ttl_seconds)
        with self._lock:
            self._store[session_id] = (user_id, expires_at)
        return session_id

    def touch_session(self, session_id: str, user_id: int, ttl_seconds: int) -> bool:
        expires_at = self._expiry(ttl_seconds)
        with self._lock:
            record = self._store.get(session_id)
            if record is None:
                return False
            stored_user_id, current_expiry = record
            if stored_user_id != user_id or current_expiry < self._now():
                self._store.pop(session_id, None)
                return False
            self._store[session_id] = (stored_user_id, expires_at)
            return True

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    @staticmethod
    def _expiry(ttl_seconds: int) -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)


_backend: Optional[SessionBackend] = None


def _get_backend() -> SessionBackend:
    global _backend
    if _backend is not None:
        return _backend

    settings = get_settings()
    try:
        backend = RedisSessionBackend(settings.redis_url)
        logger.info("Session store initialized with Redis at %s", settings.redis_url)
        _backend = backend
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning("Redis unavailable (%s), falling back to in-memory session store", exc)
        _backend = InMemorySessionBackend()
    return _backend


def create_session(user_id: int, ttl_seconds: int) -> str:
    """创建会话并返回会话 ID。"""
    return _get_backend().create_session(user_id, ttl_seconds)


def touch_session(session_id: str, user_id: int, ttl_seconds: int) -> bool:
    """刷新会话 TTL，若会话不存在或用户不匹配则返回 ``False``。"""
    return _get_backend().touch_session(session_id, user_id, ttl_seconds)


def delete_session(session_id: str) -> None:
    """删除指定会话，忽略不存在的情况。"""
    _get_backend().delete_session(session_id)
