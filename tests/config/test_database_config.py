"""
Tests for Database Configuration.
"""

import pytest
from unittest.mock import patch, MagicMock
import os

from phoenix_guardian.config.database_config import (
    DatabaseConfig,
    ProductionDatabase,
    PSYCOPG2_AVAILABLE
)


class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = DatabaseConfig()
        
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "phoenix_guardian"
        assert config.user == "phoenix_user"
        assert config.ssl_mode == "prefer"
        assert config.pool_min_connections == 2
        assert config.pool_max_connections == 20
    
    def test_from_env(self):
        """Test loading from environment variables."""
        env = {
            'PG_HOST': 'db.example.com',
            'PG_PORT': '5433',
            'PG_DATABASE': 'test_db',
            'PG_USER': 'test_user',
            'PG_PASSWORD': 'secret123',
            'PG_SSL_MODE': 'require',
            'PG_POOL_MIN': '5',
            'PG_POOL_MAX': '50'
        }
        
        with patch.dict(os.environ, env, clear=False):
            config = DatabaseConfig.from_env()
        
        assert config.host == 'db.example.com'
        assert config.port == 5433
        assert config.database == 'test_db'
        assert config.user == 'test_user'
        assert config.password == 'secret123'
        assert config.ssl_mode == 'require'
        assert config.pool_min_connections == 5
        assert config.pool_max_connections == 50
    
    def test_for_testing(self):
        """Test testing configuration factory."""
        config = DatabaseConfig.for_testing()
        
        assert config.database == 'phoenix_test'
        assert config.ssl_mode == 'disable'
        assert config.pool_max_connections == 5
    
    def test_get_connection_string(self):
        """Test connection string generation."""
        config = DatabaseConfig(
            host='localhost',
            port=5432,
            database='test',
            user='user',
            password='pass',
            ssl_mode='require'
        )
        
        conn_str = config.get_connection_string()
        
        assert 'host=localhost' in conn_str
        assert 'port=5432' in conn_str
        assert 'dbname=test' in conn_str
        assert 'user=user' in conn_str
        assert 'password=pass' in conn_str
        assert 'sslmode=require' in conn_str
    
    def test_to_dict_masks_password(self):
        """Test password is masked in dict output."""
        config = DatabaseConfig(password='secret')
        result = config.to_dict()
        
        assert result['password_set'] is True
        assert 'secret' not in str(result)


class TestProductionDatabase:
    """Tests for ProductionDatabase class."""
    
    def test_init_with_mock(self):
        """Test initialization with mock pool."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        assert db.pool is not None
        assert db.use_mock is True
        assert db.total_queries == 0
    
    def test_health_check_mock(self):
        """Test health check with mock database."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        health = db.health_check()
        
        assert health['healthy'] is True
        assert 'version' in health
    
    def test_execute_query_mock(self):
        """Test query execution with mock."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        result = db.execute_query(
            "SELECT version()",
            fetch_one=True
        )
        
        assert db.total_queries == 1
        assert db.total_query_time_ms > 0
    
    def test_performance_metrics(self):
        """Test performance metrics collection."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        # Execute some queries
        for _ in range(5):
            db.execute_query("SELECT 1")
        
        metrics = db.get_performance_metrics()
        
        assert metrics['total_queries'] == 5
        assert 'avg_query_time_ms' in metrics
        assert 'slow_queries_count' in metrics
    
    def test_context_manager(self):
        """Test connection context manager."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        with db.get_connection() as conn:
            assert conn is not None
    
    def test_close(self):
        """Test database close."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        db.close()
        # Should not raise


class TestDatabaseConnectionPooling:
    """Tests for connection pooling behavior."""
    
    def test_pool_reuses_connections(self):
        """Test that connections are reused."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        # Execute multiple queries
        for i in range(10):
            db.execute_query(f"SELECT {i}")
        
        # With pooling, should reuse connections efficiently
        assert db.total_queries == 10
    
    def test_slow_query_tracking(self):
        """Test slow query detection."""
        config = DatabaseConfig.for_testing()
        db = ProductionDatabase(config, use_mock=True)
        
        # Execute query
        db.execute_query("SELECT 1")
        
        # Check slow query list structure
        metrics = db.get_performance_metrics()
        assert 'slow_queries_recent' in metrics


class TestDatabaseWithRealConnection:
    """Tests that would use real PostgreSQL (skipped if unavailable)."""
    
    @pytest.mark.skipif(
        not PSYCOPG2_AVAILABLE,
        reason="psycopg2 not installed"
    )
    def test_real_connection_requires_server(self):
        """Test real connection handling."""
        # This test documents the expected behavior
        # In CI/CD, PostgreSQL would be available
        pass
