"""
Unit tests for src/core/cache.py

Tests Redis cache wrapper functionality including get/set operations and JSON handling.
"""

import json
from unittest.mock import MagicMock, patch

from src.core.cache import CacheClient


class TestCacheClient:
    """Test cases for CacheClient class."""

    @patch("src.core.cache.redis.Redis")
    def test_init_creates_redis_client(self, mock_redis_class):
        """Test CacheClient initialization creates Redis client."""
        cache = CacheClient()  # noqa

        # Verify Redis was called with connection_pool
        assert mock_redis_class.called
        call_kwargs = mock_redis_class.call_args[1]
        assert "connection_pool" in call_kwargs

    @patch("src.core.cache.redis.Redis")
    def test_get_existing_key(self, mock_redis_class):
        """Test getting an existing cache key."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = "cached_value"
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.get("test_key")

        assert result == "cached_value"
        mock_redis_instance.get.assert_called_once_with("test_key")

    @patch("src.core.cache.redis.Redis")
    def test_get_missing_key(self, mock_redis_class):
        """Test getting a non-existent cache key."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.get("missing_key")

        assert result is None

    @patch("src.core.cache.redis.Redis")
    def test_get_exception_handling(self, mock_redis_class):
        """Test get method handles Redis exceptions gracefully."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.side_effect = Exception("Redis connection error")
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.get("test_key")

        assert result is None  # Should return None on error

    @patch("src.core.cache.redis.Redis")
    def test_set_with_default_ttl(self, mock_redis_class):
        """Test setting a value with default TTL."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set("test_key", "test_value")

        assert result is True
        mock_redis_instance.setex.assert_called_once_with("test_key", 600, "test_value")

    @patch("src.core.cache.redis.Redis")
    def test_set_with_custom_ttl(self, mock_redis_class):
        """Test setting a value with custom TTL."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set("test_key", "test_value", ttl_seconds=1200)

        assert result is True
        mock_redis_instance.setex.assert_called_once_with(
            "test_key", 1200, "test_value"
        )

    @patch("src.core.cache.redis.Redis")
    def test_set_without_ttl(self, mock_redis_class):
        """Test setting a value without TTL (ttl_seconds=0)."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set("test_key", "test_value", ttl_seconds=0)

        assert result is True
        mock_redis_instance.set.assert_called_once_with("test_key", "test_value")

    @patch("src.core.cache.redis.Redis")
    def test_set_exception_handling(self, mock_redis_class):
        """Test set method handles Redis exceptions gracefully."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.side_effect = Exception("Redis connection error")
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set("test_key", "test_value")

        assert result is False  # Should return False on error

    @patch("src.core.cache.redis.Redis")
    def test_get_json_valid_data(self, mock_redis_class):
        """Test getting and deserializing valid JSON data."""
        test_data = {"field1": "value1", "field2": "value2"}
        json_string = json.dumps(test_data)

        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = json_string
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.get_json("test_key")

        assert result == test_data

    @patch("src.core.cache.redis.Redis")
    def test_get_json_missing_key(self, mock_redis_class):
        """Test get_json with missing cache key."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.get_json("missing_key")

        assert result is None

    @patch("src.core.cache.redis.Redis")
    def test_get_json_invalid_data(self, mock_redis_class):
        """Test get_json with invalid JSON data."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = "not valid json {"
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.get_json("test_key")

        assert result is None  # Should return None on JSON decode error

    @patch("src.core.cache.redis.Redis")
    def test_set_json_valid_data(self, mock_redis_class):
        """Test serializing and setting JSON data."""
        test_data = {"field1": "value1", "field2": "value2"}

        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set_json("test_key", test_data)

        assert result is True
        # Verify JSON was serialized correctly
        call_args = mock_redis_instance.setex.call_args
        stored_value = call_args[0][2]  # Third argument is the value
        assert json.loads(stored_value) == test_data

    @patch("src.core.cache.redis.Redis")
    def test_set_json_with_custom_ttl(self, mock_redis_class):
        """Test set_json with custom TTL."""
        test_data = {"key": "value"}

        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set_json("test_key", test_data, ttl_seconds=1800)

        assert result is True
        call_args = mock_redis_instance.setex.call_args
        assert call_args[0][1] == 1800  # Second argument is TTL

    @patch("src.core.cache.redis.Redis")
    def test_set_json_complex_data(self, mock_redis_class):
        """Test set_json with complex nested data."""
        test_data = {
            "label": "test",
            "fields": {"field1": "value1", "field2": None},
            "meta": {
                "timings": {"extract": 0.5, "llm": 2.3},
                "cache_hit": False,
            },
        }

        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set_json("test_key", test_data)

        assert result is True
        call_args = mock_redis_instance.setex.call_args
        stored_value = call_args[0][2]
        assert json.loads(stored_value) == test_data

    @patch("src.core.cache.redis.Redis")
    def test_set_json_exception_handling(self, mock_redis_class):
        """Test set_json handles exceptions gracefully."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.side_effect = Exception("Redis error")
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()
        result = cache.set_json("test_key", {"data": "value"})

        assert result is False

    @patch("src.core.cache.redis.Redis")
    def test_roundtrip_json_data(self, mock_redis_class):
        """Test complete roundtrip: set_json -> get_json."""
        test_data = {
            "label": "carteira_oab",
            "fields": {"nome": "JOÃO DA SILVA", "inscricao": "123456"},
            "meta": {"cache_hit": False},
        }

        stored_json = None

        def mock_setex(key, ttl, value):
            nonlocal stored_json
            stored_json = value
            return True

        def mock_get(key):
            return stored_json

        mock_redis_instance = MagicMock()
        mock_redis_instance.setex.side_effect = mock_setex
        mock_redis_instance.get.side_effect = mock_get
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()

        # Set and get
        cache.set_json("test_key", test_data)
        result = cache.get_json("test_key")

        assert result == test_data

    @patch("src.core.cache.redis.Redis")
    def test_cache_key_isolation(self, mock_redis_class):
        """Test that different cache keys are isolated."""
        mock_redis_instance = MagicMock()
        cache_data = {}

        def mock_get(key):
            return cache_data.get(key)

        def mock_setex(key, ttl, value):
            cache_data[key] = value
            return True

        mock_redis_instance.get.side_effect = mock_get
        mock_redis_instance.setex.side_effect = mock_setex
        mock_redis_class.return_value = mock_redis_instance

        cache = CacheClient()

        # Set different values for different keys
        cache.set_json("key1", {"value": 1})
        cache.set_json("key2", {"value": 2})

        # Verify isolation
        result1 = cache.get_json("key1")
        result2 = cache.get_json("key2")

        assert result1["value"] == 1
        assert result2["value"] == 2
