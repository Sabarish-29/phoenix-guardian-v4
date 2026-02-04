"""
Tests for ML Model Cache.
"""

import pytest
import threading
import time

from phoenix_guardian.ml.model_cache import (
    ModelCache,
    MockModel,
    MockTokenizer,
    get_cached_detector_model,
    get_cached_model,
    TRANSFORMERS_AVAILABLE
)


class TestMockModel:
    """Tests for mock model implementation."""
    
    def test_mock_model_callable(self):
        """Test mock model can be called."""
        model = MockModel("test-model")
        
        output = model(input_ids=[[101, 2000, 102]])
        
        assert hasattr(output, 'logits')
        assert len(output.logits) == 1
    
    def test_mock_model_config(self):
        """Test mock model has config."""
        model = MockModel()
        assert model.config.num_labels == 2


class TestMockTokenizer:
    """Tests for mock tokenizer implementation."""
    
    def test_mock_tokenizer_encode(self):
        """Test mock tokenizer encoding."""
        tokenizer = MockTokenizer()
        
        tokens = tokenizer.encode("Hello world")
        
        assert isinstance(tokens, list)
        assert len(tokens) > 0
    
    def test_mock_tokenizer_call(self):
        """Test mock tokenizer call."""
        tokenizer = MockTokenizer()
        
        result = tokenizer("Test text", return_tensors="pt")
        
        assert 'input_ids' in result
        assert 'attention_mask' in result
    
    def test_mock_tokenizer_batch(self):
        """Test mock tokenizer with batch input."""
        tokenizer = MockTokenizer()
        
        result = tokenizer(["Text 1", "Text 2"])
        
        assert len(result['input_ids']) == 2


class TestModelCache:
    """Tests for ModelCache singleton."""
    
    def setup_method(self):
        """Reset singleton before each test."""
        ModelCache.reset_instance()
    
    def teardown_method(self):
        """Clean up after each test."""
        ModelCache.reset_instance()
    
    def test_singleton_pattern(self):
        """Test singleton returns same instance."""
        cache1 = ModelCache.get_instance()
        cache2 = ModelCache.get_instance()
        
        assert cache1 is cache2
    
    def test_get_model_with_mock(self):
        """Test getting model with mock."""
        cache = ModelCache.get_instance()
        
        model, tokenizer = cache.get_model("test-model", use_mock=True)
        
        assert model is not None
        assert tokenizer is not None
        assert cache.cache_misses == 1
    
    def test_cache_hit(self):
        """Test cache hit on second request."""
        cache = ModelCache.get_instance()
        
        # First load
        model1, _ = cache.get_model("test-model", use_mock=True)
        
        # Second request should hit cache
        model2, _ = cache.get_model("test-model", use_mock=True)
        
        assert model1 is model2
        assert cache.cache_hits == 1
        assert cache.cache_misses == 1
    
    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = ModelCache.get_instance(max_models=2)
        
        # Load 3 models (should evict first)
        cache.get_model("model-1", use_mock=True)
        cache.get_model("model-2", use_mock=True)
        cache.get_model("model-3", use_mock=True)
        
        # First model should be evicted
        assert not cache.is_cached("model-1")
        assert cache.is_cached("model-2")
        assert cache.is_cached("model-3")
    
    def test_force_reload(self):
        """Test force reload bypasses cache."""
        cache = ModelCache.get_instance()
        
        # Initial load
        model1, _ = cache.get_model("test-model", use_mock=True)
        
        # Force reload
        model2, _ = cache.get_model("test-model", use_mock=True, force_reload=True)
        
        # Should be different instance
        assert model1 is not model2
        assert cache.cache_misses == 2
    
    def test_clear_cache(self):
        """Test clearing cache."""
        cache = ModelCache.get_instance()
        
        cache.get_model("model-1", use_mock=True)
        cache.get_model("model-2", use_mock=True)
        
        cache.clear_cache()
        
        assert len(cache.get_cached_models()) == 0
        assert cache.cache_hits == 0
        assert cache.cache_misses == 0
    
    def test_remove_model(self):
        """Test removing specific model."""
        cache = ModelCache.get_instance()
        
        cache.get_model("model-1", use_mock=True)
        cache.get_model("model-2", use_mock=True)
        
        result = cache.remove_model("model-1")
        
        assert result is True
        assert not cache.is_cached("model-1")
        assert cache.is_cached("model-2")
    
    def test_get_metrics(self):
        """Test metrics collection."""
        cache = ModelCache.get_instance()
        
        cache.get_model("model-1", use_mock=True)
        cache.get_model("model-1", use_mock=True)  # Hit
        cache.get_model("model-2", use_mock=True)
        
        metrics = cache.get_metrics()
        
        assert metrics['cache_hits'] == 1
        assert metrics['cache_misses'] == 2
        assert metrics['total_requests'] == 3
        assert metrics['hit_rate_percent'] > 30
        assert metrics['cache_size'] == 2
    
    def test_thread_safety(self):
        """Test thread-safe access to cache."""
        cache = ModelCache.get_instance()
        errors = []
        
        def load_model(name):
            try:
                cache.get_model(name, use_mock=True)
            except Exception as e:
                errors.append(str(e))
        
        threads = [
            threading.Thread(target=load_model, args=(f"model-{i}",))
            for i in range(10)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def setup_method(self):
        """Reset singleton."""
        ModelCache.reset_instance()
    
    def teardown_method(self):
        """Clean up."""
        ModelCache.reset_instance()
    
    def test_get_cached_detector_model(self):
        """Test get_cached_detector_model function."""
        model, tokenizer = get_cached_detector_model(use_mock=True)
        
        assert model is not None
        assert tokenizer is not None
    
    def test_get_cached_model(self):
        """Test get_cached_model function."""
        model, tokenizer = get_cached_model("custom-model", use_mock=True)
        
        assert model is not None
        assert tokenizer is not None


class TestModelCachePerformance:
    """Performance tests for model cache."""
    
    def setup_method(self):
        """Reset singleton."""
        ModelCache.reset_instance()
    
    def teardown_method(self):
        """Clean up."""
        ModelCache.reset_instance()
    
    def test_cache_reduces_load_time(self):
        """Test that cache significantly reduces load time."""
        cache = ModelCache.get_instance()
        
        # First load (cold)
        start = time.perf_counter()
        cache.get_model("test-model", use_mock=True)
        cold_time = time.perf_counter() - start
        
        # Second load (cached)
        start = time.perf_counter()
        cache.get_model("test-model", use_mock=True)
        hot_time = time.perf_counter() - start
        
        # Cached access should be faster (even with mock)
        assert hot_time < cold_time
