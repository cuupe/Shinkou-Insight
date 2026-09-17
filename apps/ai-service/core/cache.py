from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class CacheService:
    """Versioned async cache with Redis primary and bounded local fallback.

    Cache keys never contain raw prompts or credentials. Project-scoped
    versions make invalidation O(1): indexing an asset only increments the
    retrieval version instead of scanning keys.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        backend: str = "auto",
        redis_url: str | None = None,
        namespace: str = "shinkou-insight",
        max_entries: int = 2_000,
    ) -> None:
        self.enabled = enabled
        self.requested_backend = backend.casefold()
        self.backend = "disabled" if not enabled else "memory"
        self.redis_url = redis_url
        self.namespace = namespace
        self.max_entries = max_entries
        self._redis: Any | None = None
        self._memory: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._versions: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._errors = 0

    @classmethod
    async def create(cls, **kwargs: Any) -> "CacheService":
        service = cls(**kwargs)
        await service.start()
        return service

    async def start(self) -> None:
        if not self.enabled or self.requested_backend == "memory" or not self.redis_url:
            return
        try:
            import redis.asyncio as redis

            client = redis.from_url(self.redis_url, decode_responses=True, socket_connect_timeout=1.5, socket_timeout=2.5)
            await client.ping()
            self._redis = client
            self.backend = "redis"
        except Exception as exc:
            self._errors += 1
            self.backend = "memory"
            logger.warning("Redis cache unavailable; using bounded memory cache: %s", exc)
            if self._redis is not None:
                await self._redis.aclose()
            self._redis = None
            if self.requested_backend == "redis":
                logger.warning("CACHE_BACKEND=redis requested, but boot continues with memory fallback")

    def _key(self, scope: str, identity: Any, *, version: int | None = None) -> str:
        encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return f"{self.namespace}:v1:{scope}:{version if version is not None else 0}:{digest}"

    async def get_version(self, scope: str, identity: Any) -> int:
        version_key = self._key(f"version:{scope}", identity)
        if self._redis is not None:
            try:
                value = await self._redis.get(version_key)
                return int(value or 0)
            except Exception as exc:
                self._errors += 1
                logger.debug("cache version read failed: %s", exc)
        return int(self._versions.get(version_key, 0))

    async def bump_version(self, scope: str, identity: Any) -> int:
        version_key = self._key(f"version:{scope}", identity)
        if self._redis is not None:
            try:
                return int(await self._redis.incr(version_key))
            except Exception as exc:
                self._errors += 1
                logger.debug("cache version increment failed: %s", exc)
        async with self._lock:
            value = int(self._versions.get(version_key, 0)) + 1
            self._versions[version_key] = value
            return value

    async def get(self, scope: str, identity: Any, *, version: int | None = None) -> Any | None:
        if not self.enabled:
            self._misses += 1
            return None
        key = self._key(scope, identity, version=version)
        value: Any | None = None
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
                value = json.loads(raw) if raw is not None else None
            except Exception as exc:
                self._errors += 1
                logger.debug("redis cache read failed: %s", exc)
        else:
            async with self._lock:
                item = self._memory.get(key)
                if item and item[0] > time.monotonic():
                    self._memory.move_to_end(key)
                    value = item[1]
                elif item:
                    self._memory.pop(key, None)
        if value is None:
            self._misses += 1
        else:
            self._hits += 1
        return value

    async def set(self, scope: str, identity: Any, value: Any, *, ttl_seconds: int, version: int | None = None) -> None:
        if not self.enabled:
            return
        key = self._key(scope, identity, version=version)
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        try:
            if self._redis is not None:
                await self._redis.set(key, payload, ex=max(1, int(ttl_seconds)))
            else:
                async with self._lock:
                    self._memory[key] = (time.monotonic() + max(1, int(ttl_seconds)), value)
                    self._memory.move_to_end(key)
                    while len(self._memory) > self.max_entries:
                        self._memory.popitem(last=False)
            self._sets += 1
        except Exception as exc:
            self._errors += 1
            logger.debug("cache write failed: %s", exc)

    async def delete(self, scope: str, identity: Any, *, version: int | None = None) -> None:
        key = self._key(scope, identity, version=version)
        if self._redis is not None:
            try:
                await self._redis.delete(key)
            except Exception as exc:
                self._errors += 1
        async with self._lock:
            self._memory.pop(key, None)

    async def get_or_set(
        self,
        scope: str,
        identity: Any,
        factory: Callable[[], Awaitable[Any]],
        *,
        ttl_seconds: int,
        version: int | None = None,
    ) -> tuple[Any, bool]:
        cached = await self.get(scope, identity, version=version)
        if cached is not None:
            return cached, True
        lock_key = self._key(scope, identity, version=version)
        async with self._lock:
            lock = self._locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            cached = await self.get(scope, identity, version=version)
            if cached is not None:
                return cached, True
            value = await factory()
            await self.set(scope, identity, value, ttl_seconds=ttl_seconds, version=version)
            return value, False

    async def stats(self) -> dict[str, Any]:
        async with self._lock:
            memory_entries = len(self._memory)
        total = self._hits + self._misses
        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "namespace": self.namespace,
            "memoryEntries": memory_entries,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "errors": self._errors,
            "hitRate": round(self._hits / total, 4) if total else 0.0,
        }

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
