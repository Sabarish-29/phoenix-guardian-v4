"""
Phoenix Guardian - Tenant-Scoped Redis Cache
Provides namespaced caching with tenant isolation.

All cache keys are automatically prefixed with tenant ID
to prevent cross-tenant data leakage.
"""

import logging
import json
import hashlib
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from functools import wraps
from enum import Enum

from phoenix_guardian.core.tenant_context import TenantContext, SecurityError

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ==============================================================================
# Redis Mock for Development
# ==============================================================================

class MockRedis:
    """
    Mock Redis client for testing and development.
    
    In production, replace with actual redis.Redis client.
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, datetime] = {}
    
    def get(self, key: str) -> Optional[bytes]:
        self._check_expiry(key)
        value = self._data.get(key)
        return value.encode() if isinstance(value, str) else value
    
    def set(
        self,
        key: str,
        value: Union[str, bytes],
        ex: Optional[int] = None,
        px: Optional[int] = None,
    ) -> bool:
        self._data[key] = value if isinstance(value, str) else value.decode()
        
        if ex:
            self._expiry[key] = datetime.now(timezone.utc) + timedelta(seconds=ex)
        elif px:
            self._expiry[key] = datetime.now(timezone.utc) + timedelta(milliseconds=px)
        
        return True
    
    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._expiry.pop(key, None)
                count += 1
        return count
    
    def exists(self, *keys: str) -> int:
        self._check_all_expiry()
        return sum(1 for key in keys if key in self._data)
    
    def keys(self, pattern: str = "*") -> List[bytes]:
        self._check_all_expiry()
        import fnmatch
        return [k.encode() for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]
    
    def scan_iter(self, match: str = "*", count: int = 100):
        for key in self.keys(match):
            yield key
    
    def expire(self, key: str, seconds: int) -> bool:
        if key in self._data:
            self._expiry[key] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            return True
        return False
    
    def ttl(self, key: str) -> int:
        if key not in self._data:
            return -2
        if key not in self._expiry:
            return -1
        
        remaining = (self._expiry[key] - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(remaining))
    
    def incr(self, key: str) -> int:
        value = int(self._data.get(key, 0)) + 1
        self._data[key] = str(value)
        return value
    
    def incrby(self, key: str, amount: int) -> int:
        value = int(self._data.get(key, 0)) + amount
        self._data[key] = str(value)
        return value
    
    def hget(self, name: str, key: str) -> Optional[bytes]:
        hash_data = self._data.get(name, {})
        value = hash_data.get(key)
        return value.encode() if value else None
    
    def hset(self, name: str, key: str, value: Union[str, bytes]) -> int:
        if name not in self._data:
            self._data[name] = {}
        self._data[name][key] = value if isinstance(value, str) else value.decode()
        return 1
    
    def hgetall(self, name: str) -> Dict[bytes, bytes]:
        hash_data = self._data.get(name, {})
        return {k.encode(): v.encode() for k, v in hash_data.items()}
    
    def hdel(self, name: str, *keys: str) -> int:
        if name not in self._data:
            return 0
        count = 0
        for key in keys:
            if key in self._data[name]:
                del self._data[name][key]
                count += 1
        return count
    
    def pipeline(self):
        return MockPipeline(self)
    
    def _check_expiry(self, key: str) -> None:
        if key in self._expiry:
            if datetime.now(timezone.utc) > self._expiry[key]:
                del self._data[key]
                del self._expiry[key]
    
    def _check_all_expiry(self) -> None:
        expired = [
            k for k, exp in self._expiry.items()
            if datetime.now(timezone.utc) > exp
        ]
        for key in expired:
            self._data.pop(key, None)
            self._expiry.pop(key, None)


class MockPipeline:
    """Mock Redis pipeline."""
    
    def __init__(self, redis: MockRedis):
        self._redis = redis
        self._commands: List[tuple] = []
    
    def get(self, key: str) -> "MockPipeline":
        self._commands.append(('get', key))
        return self
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> "MockPipeline":
        self._commands.append(('set', key, value, ex))
        return self
    
    def delete(self, key: str) -> "MockPipeline":
        self._commands.append(('delete', key))
        return self
    
    def execute(self) -> List[Any]:
        results = []
        for cmd in self._commands:
            if cmd[0] == 'get':
                results.append(self._redis.get(cmd[1]))
            elif cmd[0] == 'set':
                results.append(self._redis.set(cmd[1], cmd[2], ex=cmd[3]))
            elif cmd[0] == 'delete':
                results.append(self._redis.delete(cmd[1]))
        self._commands = []
        return results


# ==============================================================================
# Tenant Redis Client
# ==============================================================================

@dataclass
class TenantCacheConfig:
    """Configuration for tenant-scoped cache."""
    
    # Key prefix
    key_prefix: str = "phoenix"
    
    # Default TTL
    default_ttl_seconds: int = 3600  # 1 hour
    
    # Tenant isolation
    enforce_tenant: bool = True
    
    # Serialization
    serializer: str = "json"  # json or pickle
    
    # Rate limiting
    max_keys_per_tenant: int = 100000
    max_memory_per_tenant_mb: float = 100.0


class TenantRedis:
    """
    Tenant-scoped Redis client with automatic key namespacing.
    
    All keys are prefixed with: {prefix}:{tenant_id}:{key}
    
    This ensures:
    1. Complete tenant isolation
    2. Easy bulk invalidation per tenant
    3. No cross-tenant data leakage
    
    Example:
        redis_client = TenantRedis(MockRedis())
        
        TenantContext.set("pilot_hospital_001")
        
        # Key becomes: phoenix:pilot_hospital_001:patient:123
        redis_client.set("patient:123", {"name": "John Doe"})
        
        # Only returns data for current tenant
        data = redis_client.get("patient:123")
    """
    
    def __init__(
        self,
        redis_client,
        config: Optional[TenantCacheConfig] = None,
    ):
        """
        Initialize tenant-scoped Redis client.
        
        Args:
            redis_client: Redis client (or MockRedis for testing)
            config: Cache configuration
        """
        self._redis = redis_client
        self._config = config or TenantCacheConfig()
    
    # =========================================================================
    # Key Management
    # =========================================================================
    
    def _get_tenant_id(self) -> str:
        """Get current tenant ID."""
        if self._config.enforce_tenant:
            return TenantContext.get()
        
        try:
            return TenantContext.get()
        except SecurityError:
            return "__global__"
    
    def _make_key(self, key: str) -> str:
        """
        Create tenant-namespaced key.
        
        Format: {prefix}:{tenant_id}:{key}
        """
        tenant_id = self._get_tenant_id()
        return f"{self._config.key_prefix}:{tenant_id}:{key}"
    
    def _make_pattern(self, pattern: str) -> str:
        """Create tenant-scoped pattern for scanning."""
        tenant_id = self._get_tenant_id()
        return f"{self._config.key_prefix}:{tenant_id}:{pattern}"
    
    def _extract_key(self, full_key: str) -> str:
        """Extract original key from namespaced key."""
        parts = full_key.split(":", 2)
        return parts[2] if len(parts) > 2 else full_key
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for storage."""
        if self._config.serializer == "json":
            return json.dumps(value, default=str)
        else:
            import pickle
            return pickle.dumps(value).hex()
    
    def _deserialize(self, data: Optional[bytes]) -> Any:
        """Deserialize value from storage."""
        if data is None:
            return None
        
        if isinstance(data, bytes):
            data = data.decode()
        
        if self._config.serializer == "json":
            return json.loads(data)
        else:
            import pickle
            return pickle.loads(bytes.fromhex(data))
    
    # =========================================================================
    # Basic Operations
    # =========================================================================
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value for key (tenant-scoped).
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        full_key = self._make_key(key)
        data = self._redis.get(full_key)
        return self._deserialize(data)
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value for key (tenant-scoped).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not provided)
        
        Returns:
            True if successful
        """
        full_key = self._make_key(key)
        ttl = ttl or self._config.default_ttl_seconds
        serialized = self._serialize(value)
        
        return self._redis.set(full_key, serialized, ex=ttl)
    
    def delete(self, key: str) -> bool:
        """
        Delete key (tenant-scoped).
        
        Args:
            key: Cache key
        
        Returns:
            True if key was deleted
        """
        full_key = self._make_key(key)
        return self._redis.delete(full_key) > 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists (tenant-scoped)."""
        full_key = self._make_key(key)
        return self._redis.exists(full_key) > 0
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple keys at once.
        
        Args:
            keys: List of cache keys
        
        Returns:
            Dictionary mapping key to value
        """
        result = {}
        pipeline = self._redis.pipeline()
        
        for key in keys:
            full_key = self._make_key(key)
            pipeline.get(full_key)
        
        values = pipeline.execute()
        
        for key, value in zip(keys, values):
            if value is not None:
                result[key] = self._deserialize(value)
        
        return result
    
    def set_many(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set multiple keys at once.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time-to-live in seconds
        
        Returns:
            True if all successful
        """
        ttl = ttl or self._config.default_ttl_seconds
        pipeline = self._redis.pipeline()
        
        for key, value in mapping.items():
            full_key = self._make_key(key)
            serialized = self._serialize(value)
            pipeline.set(full_key, serialized, ex=ttl)
        
        results = pipeline.execute()
        return all(results)
    
    def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys.
        
        Args:
            keys: List of cache keys
        
        Returns:
            Number of keys deleted
        """
        full_keys = [self._make_key(key) for key in keys]
        return self._redis.delete(*full_keys)
    
    # =========================================================================
    # Pattern Operations
    # =========================================================================
    
    def keys(self, pattern: str = "*") -> List[str]:
        """
        Get all keys matching pattern (tenant-scoped).
        
        Args:
            pattern: Key pattern (e.g., "patient:*")
        
        Returns:
            List of matching keys (without tenant prefix)
        """
        full_pattern = self._make_pattern(pattern)
        full_keys = self._redis.keys(full_pattern)
        
        return [
            self._extract_key(k.decode() if isinstance(k, bytes) else k)
            for k in full_keys
        ]
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.
        
        Args:
            pattern: Key pattern to invalidate
        
        Returns:
            Number of keys deleted
        """
        keys = self.keys(pattern)
        if not keys:
            return 0
        
        return self.delete_many(keys)
    
    def invalidate_all(self) -> int:
        """
        Invalidate ALL cache entries for current tenant.
        
        Use with caution - this clears the entire tenant cache.
        
        Returns:
            Number of keys deleted
        """
        return self.invalidate_pattern("*")
    
    # =========================================================================
    # Hash Operations
    # =========================================================================
    
    def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field value."""
        full_name = self._make_key(name)
        data = self._redis.hget(full_name, key)
        return self._deserialize(data)
    
    def hset(self, name: str, key: str, value: Any) -> int:
        """Set hash field value."""
        full_name = self._make_key(name)
        serialized = self._serialize(value)
        return self._redis.hset(full_name, key, serialized)
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all hash fields."""
        full_name = self._make_key(name)
        data = self._redis.hgetall(full_name)
        
        return {
            k.decode() if isinstance(k, bytes) else k: self._deserialize(v)
            for k, v in data.items()
        }
    
    # =========================================================================
    # Counter Operations
    # =========================================================================
    
    def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        full_key = self._make_key(key)
        if amount == 1:
            return self._redis.incr(full_key)
        return self._redis.incrby(full_key, amount)
    
    # =========================================================================
    # Cache-Aside Pattern
    # =========================================================================
    
    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[int] = None,
    ) -> T:
        """
        Get value from cache or compute and store it.
        
        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds
        
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        
        if value is not None:
            logger.debug(f"Cache hit: {key}")
            return value
        
        logger.debug(f"Cache miss: {key}")
        value = factory()
        self.set(key, value, ttl=ttl)
        
        return value


# ==============================================================================
# Cache Decorators
# ==============================================================================

def cached(
    redis_client: TenantRedis,
    key_prefix: str,
    ttl: Optional[int] = None,
):
    """
    Decorator for caching function results.
    
    The cache key is generated from the function name and arguments.
    Results are automatically tenant-scoped.
    
    Example:
        @cached(redis_client, "predictions", ttl=300)
        def get_patient_predictions(patient_id: str) -> List[dict]:
            return db.query(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function and arguments
            key_parts = [key_prefix, func.__name__]
            
            for arg in args:
                key_parts.append(str(arg))
            
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")
            
            cache_key = ":".join(key_parts)
            
            # Try cache first
            cached_value = redis_client.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = func(*args, **kwargs)
            redis_client.set(cache_key, result, ttl=ttl)
            
            return result
        
        # Add cache control methods
        wrapper.invalidate = lambda *args, **kwargs: redis_client.delete(
            ":".join([key_prefix, func.__name__] + [str(a) for a in args])
        )
        
        return wrapper
    return decorator


def cached_property(
    redis_client: TenantRedis,
    key_prefix: str,
    ttl: Optional[int] = None,
):
    """
    Decorator for caching object properties.
    
    Example:
        class PatientService:
            @cached_property(redis_client, "patient")
            def latest_vitals(self) -> dict:
                return self._fetch_vitals()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Use object ID in cache key if available
            obj_id = getattr(self, 'id', None) or id(self)
            cache_key = f"{key_prefix}:{func.__name__}:{obj_id}"
            
            # Try cache
            cached_value = redis_client.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = func(self, *args, **kwargs)
            redis_client.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


# ==============================================================================
# Cache Invalidation
# ==============================================================================

class CacheInvalidator:
    """
    Manages cache invalidation for tenant data.
    
    Provides methods to invalidate cache when data changes,
    ensuring consistency between cache and database.
    """
    
    def __init__(self, redis_client: TenantRedis):
        """
        Initialize cache invalidator.
        
        Args:
            redis_client: Tenant-scoped Redis client
        """
        self._redis = redis_client
        self._invalidation_patterns: Dict[str, List[str]] = {}
    
    def register_pattern(self, entity: str, patterns: List[str]) -> None:
        """
        Register cache patterns for an entity.
        
        When the entity is invalidated, all registered patterns are cleared.
        
        Args:
            entity: Entity name (e.g., "patient", "prediction")
            patterns: Cache key patterns to invalidate
        """
        self._invalidation_patterns[entity] = patterns
    
    def invalidate_entity(self, entity: str, entity_id: str) -> int:
        """
        Invalidate cache for a specific entity.
        
        Args:
            entity: Entity name
            entity_id: Specific entity ID
        
        Returns:
            Number of keys invalidated
        """
        patterns = self._invalidation_patterns.get(entity, [])
        total = 0
        
        for pattern in patterns:
            # Replace placeholders
            resolved_pattern = pattern.replace("{id}", entity_id)
            total += self._redis.invalidate_pattern(resolved_pattern)
        
        # Also invalidate entity-specific key
        total += self._redis.delete(f"{entity}:{entity_id}") if self._redis.exists(f"{entity}:{entity_id}") else 0
        
        logger.info(f"Invalidated {total} cache keys for {entity}:{entity_id}")
        return total
    
    def invalidate_entity_type(self, entity: str) -> int:
        """
        Invalidate ALL cache entries for an entity type.
        
        Args:
            entity: Entity name
        
        Returns:
            Number of keys invalidated
        """
        total = self._redis.invalidate_pattern(f"{entity}:*")
        
        logger.info(f"Invalidated {total} cache keys for entity type {entity}")
        return total
    
    def invalidate_tenant(self) -> int:
        """
        Invalidate ALL cache entries for current tenant.
        
        Use when tenant data is bulk-updated or during maintenance.
        
        Returns:
            Number of keys invalidated
        """
        total = self._redis.invalidate_all()
        
        tenant_id = TenantContext.get()
        logger.warning(f"Invalidated ALL {total} cache keys for tenant {tenant_id}")
        
        return total


# ==============================================================================
# Feature Cache
# ==============================================================================

class TenantFeatureCache:
    """
    Specialized cache for ML features.
    
    Optimized for caching patient features used in predictions.
    """
    
    def __init__(
        self,
        redis_client: TenantRedis,
        ttl_seconds: int = 300,
    ):
        """
        Initialize feature cache.
        
        Args:
            redis_client: Tenant-scoped Redis client
            ttl_seconds: Default TTL for features
        """
        self._redis = redis_client
        self._ttl = ttl_seconds
    
    def get_patient_features(
        self,
        patient_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached features for a patient.
        
        Args:
            patient_id: Patient identifier
        
        Returns:
            Cached features or None
        """
        return self._redis.get(f"features:patient:{patient_id}")
    
    def set_patient_features(
        self,
        patient_id: str,
        features: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache features for a patient.
        
        Args:
            patient_id: Patient identifier
            features: Feature dictionary
            ttl: Optional custom TTL
        
        Returns:
            True if successful
        """
        return self._redis.set(
            f"features:patient:{patient_id}",
            features,
            ttl=ttl or self._ttl,
        )
    
    def invalidate_patient_features(self, patient_id: str) -> bool:
        """Invalidate cached features for a patient."""
        return self._redis.delete(f"features:patient:{patient_id}")
    
    def bulk_get_features(
        self,
        patient_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get features for multiple patients.
        
        Args:
            patient_ids: List of patient IDs
        
        Returns:
            Dictionary mapping patient_id to features
        """
        keys = [f"features:patient:{pid}" for pid in patient_ids]
        results = self._redis.get_many(keys)
        
        return {
            pid: results.get(f"features:patient:{pid}")
            for pid in patient_ids
            if f"features:patient:{pid}" in results
        }
    
    def bulk_set_features(
        self,
        features_by_patient: Dict[str, Dict[str, Any]],
    ) -> bool:
        """
        Cache features for multiple patients.
        
        Args:
            features_by_patient: Dictionary mapping patient_id to features
        
        Returns:
            True if all successful
        """
        mapping = {
            f"features:patient:{pid}": features
            for pid, features in features_by_patient.items()
        }
        return self._redis.set_many(mapping, ttl=self._ttl)
