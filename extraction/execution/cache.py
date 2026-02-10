"""
Caching Support for Execution Model Extraction

Provides caching of PDF text extraction and LLM responses
to improve performance on repeated extractions.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "protocol2usdm" / "execution"


@dataclass
class CacheEntry:
    """A cached result entry."""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        return cls(**data)


class ExecutionCache:
    """
    Cache for execution model extraction results.
    
    Caches:
    - PDF text extraction results
    - LLM responses
    - Intermediate extraction results
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 86400 * 7,  # 7 days default
        enabled: bool = True,
    ):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory for cache files
            ttl_seconds: Time-to-live for cache entries
            enabled: Whether caching is enabled
        """
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._memory_cache: Dict[str, CacheEntry] = {}
        
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments.

        The key incorporates all positional and keyword arguments so that
        different models, prompts, or inputs produce distinct keys.
        """
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    @staticmethod
    def make_key(
        func_name: str,
        *,
        model: str = "",
        prompt_hash: str = "",
        **extra,
    ) -> str:
        """Build a deterministic cache key that includes model + prompt hash.

        This is the recommended way to create keys for LLM-backed extractors
        so that switching models or editing prompts automatically invalidates
        stale entries.

        Args:
            func_name: Logical name of the extractor / function.
            model: LLM model identifier (e.g. ``gemini-2.5-pro``).
            prompt_hash: Truncated SHA-256 of the prompt text.  Use
                :func:`hash_prompt` to compute this.
            **extra: Any additional discriminators (pdf_path, pages, etc.).

        Returns:
            16-char hex digest suitable for use as a cache key.
        """
        key_data = json.dumps(
            {"fn": func_name, "model": model, "prompt": prompt_hash, **extra},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        return self.cache_dir / f"{key}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None
        
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if not entry.is_expired():
                return entry.value
            else:
                del self._memory_cache[key]
        
        # Check disk cache
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                entry = CacheEntry.from_dict(data)
                
                if not entry.is_expired():
                    # Store in memory cache
                    self._memory_cache[key] = entry
                    return entry.value
                else:
                    # Remove expired entry
                    cache_path.unlink()
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load cache entry {key}: {e}")
                cache_path.unlink(missing_ok=True)
        
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Custom TTL (uses default if not specified)
            metadata: Optional metadata to store
        """
        if not self.enabled:
            return
        
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        now = time.time()
        
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + ttl if ttl > 0 else None,
            metadata=metadata,
        )
        
        # Store in memory
        self._memory_cache[key] = entry
        
        # Store on disk
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, indent=2, default=str)
        except (IOError, TypeError) as e:
            logger.warning(f"Failed to write cache entry {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        deleted = False
        
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True
        
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            deleted = True
        
        return deleted
    
    def clear(self) -> int:
        """Clear all cache entries. Returns count of entries cleared."""
        count = len(self._memory_cache)
        self._memory_cache.clear()
        
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        disk_count = 0
        disk_size = 0
        
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                disk_count += 1
                disk_size += cache_file.stat().st_size
        
        return {
            "memory_entries": len(self._memory_cache),
            "disk_entries": disk_count,
            "disk_size_bytes": disk_size,
            "cache_dir": str(self.cache_dir),
            "enabled": self.enabled,
        }


# Global cache instance
_global_cache: Optional[ExecutionCache] = None


def get_cache() -> ExecutionCache:
    """Get the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ExecutionCache()
    return _global_cache


def set_cache(cache: ExecutionCache) -> None:
    """Set the global cache instance."""
    global _global_cache
    _global_cache = cache


def hash_prompt(prompt_text: str) -> str:
    """Return a 12-char hex digest of *prompt_text*.

    Suitable for embedding in cache keys so that prompt edits
    automatically invalidate stale cached LLM responses.
    """
    return hashlib.sha256(prompt_text.encode()).hexdigest()[:12]


def cached(
    key_prefix: str = "",
    ttl_seconds: Optional[int] = None,
    include_model: bool = True,
    prompt_text: Optional[str] = None,
) -> Callable:
    """
    Decorator to cache function results.

    Cache keys now incorporate the ``model`` kwarg (if present) and an
    optional prompt hash so that switching models or editing prompts
    produces a cache miss instead of returning stale data.
    
    Args:
        key_prefix: Prefix for cache keys
        ttl_seconds: Custom TTL for this function
        include_model: If True, include the ``model`` kwarg in the key
        prompt_text: If provided, its hash is folded into the key
        
    Returns:
        Decorated function
    """
    _prompt_hash = hash_prompt(prompt_text) if prompt_text else ""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key — model + prompt aware
            key_data = {
                "prefix": key_prefix or func.__name__,
                "args": args[1:] if args else [],  # Skip 'self' if present
                "kwargs": kwargs,
            }
            if include_model and "model" in kwargs:
                key_data["_model"] = kwargs["model"]
            if _prompt_hash:
                key_data["_prompt"] = _prompt_hash
            key = hashlib.sha256(
                json.dumps(key_data, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            
            # Check cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__} (key={key})")
                return cached_value
            
            # Call function
            result = func(*args, **kwargs)
            
            # Store in cache with model metadata
            metadata = {}
            if "model" in kwargs:
                metadata["model"] = kwargs["model"]
            if _prompt_hash:
                metadata["prompt_hash"] = _prompt_hash
            cache.set(key, result, ttl_seconds=ttl_seconds,
                      metadata=metadata if metadata else None)
            logger.debug(f"Cached result for {func.__name__} (key={key})")
            
            return result
        
        return wrapper
    return decorator


def cache_pdf_text(
    pdf_path: str,
    pages: Optional[list] = None,
    model: str = "",
) -> str:
    """
    Get cached PDF text or extract and cache it.
    
    Args:
        pdf_path: Path to PDF file
        pages: Optional list of page numbers
        model: LLM model name (included in key for model-specific caching)
        
    Returns:
        Cached key for the PDF text
    """
    # Generate key based on file path, modification time, and model
    path = Path(pdf_path)
    if not path.exists():
        return ""
    
    mtime = path.stat().st_mtime
    key_data = f"{pdf_path}:{mtime}:{pages}:{model}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]
