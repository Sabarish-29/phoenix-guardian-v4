"""
ML Model Caching System.

Problem: ML models take 2-3 seconds to load from disk.
Solution: Cache loaded models in memory, reuse across requests.

Performance Impact:
- Before: 2-3s model load per request
- After: 0ms (cached) or 2-3s (first load only)
"""

import time
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from collections import OrderedDict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import transformers
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available, using mock models")


@dataclass
class CachedModel:
    """Cached model metadata."""
    name: str
    model: Any
    tokenizer: Any
    load_time_seconds: float
    access_count: int = 0
    last_accessed: float = 0.0


class MockModel:
    """Mock ML model for testing without transformers."""
    
    def __init__(self, name: str = "mock-model"):
        self.name = name
        self.config = type('Config', (), {'num_labels': 2})()
    
    def __call__(self, **kwargs):
        import torch
        batch_size = kwargs.get('input_ids', [[]]).__len__() if hasattr(kwargs.get('input_ids', []), '__len__') else 1
        return type('Output', (), {'logits': [[0.1, 0.9]] * batch_size})()


class MockTokenizer:
    """Mock tokenizer for testing without transformers."""
    
    def __init__(self, name: str = "mock-tokenizer"):
        self.name = name
    
    def __call__(self, text, **kwargs):
        if isinstance(text, str):
            text = [text]
        return {
            'input_ids': [[101, 2000, 102]] * len(text),
            'attention_mask': [[1, 1, 1]] * len(text)
        }
    
    def encode(self, text, **kwargs):
        return [101, 2000, 102]
    
    def decode(self, ids, **kwargs):
        return "decoded text"


class ModelCache:
    """Thread-safe LRU cache for ML models."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, max_models: int = 3):
        """Initialize model cache."""
        self.max_models = max_models
        self._cache: OrderedDict[str, CachedModel] = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_load_time_seconds = 0.0
    
    @classmethod
    def get_instance(cls, max_models: int = 3) -> 'ModelCache':
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(max_models)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear_cache()
            cls._instance = None
    
    def get_model(
        self,
        model_name: str,
        force_reload: bool = False,
        use_mock: bool = False
    ) -> Tuple[Any, Any]:
        """Get model and tokenizer (cached or loaded)."""
        with self._cache_lock:
            # Check cache
            if not force_reload and model_name in self._cache:
                self.cache_hits += 1
                cached = self._cache[model_name]
                cached.access_count += 1
                cached.last_accessed = time.time()
                
                # Move to end (most recently used)
                self._cache.move_to_end(model_name)
                
                logger.debug(f"Model cache HIT: {model_name}")
                return cached.model, cached.tokenizer
            
            # Cache miss
            self.cache_misses += 1
            logger.info(f"Model cache MISS: {model_name}")
            
            start_time = time.perf_counter()
            
            # Load model
            if use_mock or not TRANSFORMERS_AVAILABLE:
                model = MockModel(model_name)
                tokenizer = MockTokenizer(model_name)
            else:
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            load_time = time.perf_counter() - start_time
            self.total_load_time_seconds += load_time
            
            # Cache the model
            self._cache[model_name] = CachedModel(
                name=model_name,
                model=model,
                tokenizer=tokenizer,
                load_time_seconds=load_time,
                access_count=1,
                last_accessed=time.time()
            )
            
            # Evict LRU if over limit
            while len(self._cache) > self.max_models:
                oldest = next(iter(self._cache))
                logger.info(f"Evicting LRU model: {oldest}")
                del self._cache[oldest]
            
            logger.info(f"Model loaded in {load_time:.2f}s: {model_name}")
            return model, tokenizer
    
    def is_cached(self, model_name: str) -> bool:
        """Check if model is in cache."""
        with self._cache_lock:
            return model_name in self._cache
    
    def clear_cache(self):
        """Clear all cached models."""
        with self._cache_lock:
            self._cache.clear()
            self.cache_hits = 0
            self.cache_misses = 0
            logger.info("Model cache cleared")
    
    def remove_model(self, model_name: str) -> bool:
        """Remove specific model from cache."""
        with self._cache_lock:
            if model_name in self._cache:
                del self._cache[model_name]
                return True
            return False
    
    def get_cached_models(self) -> list:
        """Get list of cached model names."""
        with self._cache_lock:
            return list(self._cache.keys())
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        with self._cache_lock:
            total = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
            
            return {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'total_requests': total,
                'hit_rate_percent': round(hit_rate, 1),
                'cached_models': self.get_cached_models(),
                'cache_size': len(self._cache),
                'max_models': self.max_models,
                'total_load_time_seconds': round(self.total_load_time_seconds, 2)
            }


def get_cached_detector_model(use_mock: bool = False) -> Tuple[Any, Any]:
    """Get ML detector model from cache."""
    cache = ModelCache.get_instance()
    model_name = "distilbert-base-uncased-finetuned-sst-2-english"
    return cache.get_model(model_name, use_mock=use_mock)


def get_cached_model(model_name: str, use_mock: bool = False) -> Tuple[Any, Any]:
    """Get any model from cache by name."""
    cache = ModelCache.get_instance()
    return cache.get_model(model_name, use_mock=use_mock)


__all__ = [
    'ModelCache',
    'MockModel',
    'MockTokenizer',
    'get_cached_detector_model',
    'get_cached_model',
    'TRANSFORMERS_AVAILABLE'
]
