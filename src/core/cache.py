"""
Lightweight cache abstraction.
Initially targets Redis via environment variables, but could be swapped.
"""

import os
from typing import Optional
import json
from src.config.settings import settings

import redis  # type: ignore


class CacheClient:
    """Thin wrapper around Redis for simple get/set operations."""

    def __init__(self) -> None:
        host = settings.redis_host
        port = settings.redis_port
        self._client = redis.Redis(host=host, port=port, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        """Return cached string payload, or None when missing."""
        try:
            return self._client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, ttl_seconds: int = 600) -> bool:
        """Set a cache entry with an optional TTL."""
        try:
            if ttl_seconds > 0:
                return bool(self._client.setex(key, ttl_seconds, value))
            return bool(self._client.set(key, value))
        except Exception:
            return False

    def get_json(self, key: str):
        """Convenience: fetch and decode JSON, or None."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, obj, ttl_seconds: int = 600) -> bool:
        """Convenience: encode JSON and store."""
        try:
            return self.set(key, json.dumps(obj), ttl_seconds)
        except Exception:
            return False
