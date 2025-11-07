"""
Production-ready Redis cache client with connection pooling and retry logic.
"""

import json
import logging
from typing import Optional

import redis  # type: ignore
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Global connection pool (shared across all CacheClient instances)
_connection_pool: Optional[redis.ConnectionPool] = None


def get_connection_pool() -> redis.ConnectionPool:
    """Get or create the global Redis connection pool."""
    global _connection_pool
    if _connection_pool is None:
        logger.info(
            f"Creating Redis connection pool: {settings.redis_host}:{settings.redis_port} "
            f"(SSL={settings.redis_ssl}, max_connections={settings.redis_max_connections})"
        )

        # Connection pool configuration
        pool_kwargs = {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "decode_responses": True,
            "max_connections": settings.redis_max_connections,
            "socket_timeout": settings.redis_socket_timeout,
            "socket_connect_timeout": settings.redis_socket_connect_timeout,
            "retry": Retry(ExponentialBackoff(), 3),
            "health_check_interval": 30,
        }

        # Add password if configured
        if settings.redis_password:
            pool_kwargs["password"] = settings.redis_password

        # Configure SSL/TLS for production (e.g., AWS ElastiCache with encryption)
        if settings.redis_ssl:
            pool_kwargs["ssl"] = True
            pool_kwargs["ssl_cert_reqs"] = "required"

        _connection_pool = redis.ConnectionPool(**pool_kwargs)

    return _connection_pool


class CacheClient:
    """Production-ready Redis cache wrapper with connection pooling and JSON serialization."""

    def __init__(self) -> None:
        """Initialize Redis client with connection pool."""
        try:
            pool = get_connection_pool()
            self._client = redis.Redis(connection_pool=pool)
            # Test connection
            self._client.ping()
            logger.debug("Redis connection established successfully")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis client: {e}")
            raise

    def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        """Return cached string payload, or None when missing."""
        try:
            return self._client.get(key)
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error on get({key}): {e}")
            return None
        except redis.TimeoutError as e:
            logger.error(f"Redis timeout on get({key}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error on get({key}): {e}")
            return None

    def set(self, key: str, value: str, ttl_seconds: int = 600) -> bool:
        """Set a cache entry with an optional TTL."""
        try:
            if ttl_seconds > 0:
                return bool(self._client.setex(key, ttl_seconds, value))
            return bool(self._client.set(key, value))
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error on set({key}): {e}")
            return False
        except redis.TimeoutError as e:
            logger.error(f"Redis timeout on set({key}): {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error on set({key}): {e}")
            return False

    def get_json(self, key: str):
        """Convenience: fetch and decode JSON, or None."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error decoding JSON for key {key}: {e}")
            return None

    def set_json(self, key: str, obj, ttl_seconds: int = 600) -> bool:
        """Convenience: encode JSON and store."""
        try:
            return self.set(key, json.dumps(obj), ttl_seconds)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to encode JSON for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error encoding JSON for key {key}: {e}")
            return False
