"""
Production PostgreSQL Database Configuration.

Features:
- Connection pooling (psycopg2.pool)
- SSL/TLS connections
- Health checks & monitoring
- Query performance logging
"""

import os
import time
import logging
from typing import Optional, Dict, Any, Generator
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import psycopg2
try:
    import psycopg2
    from psycopg2 import pool, extras
    from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available, using mock database")


@dataclass
class DatabaseConfig:
    """PostgreSQL connection configuration."""
    
    host: str = "localhost"
    port: int = 5432
    database: str = "phoenix_guardian"
    user: str = "phoenix_user"
    password: str = ""
    ssl_mode: str = "prefer"
    pool_min_connections: int = 2
    pool_max_connections: int = 20
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv('PG_HOST', 'localhost'),
            port=int(os.getenv('PG_PORT', '5432')),
            database=os.getenv('PG_DATABASE', 'phoenix_guardian'),
            user=os.getenv('PG_USER', 'phoenix_user'),
            password=os.getenv('PG_PASSWORD', ''),
            ssl_mode=os.getenv('PG_SSL_MODE', 'prefer'),
            pool_min_connections=int(os.getenv('PG_POOL_MIN', '2')),
            pool_max_connections=int(os.getenv('PG_POOL_MAX', '20'))
        )
    
    @classmethod
    def for_testing(cls) -> 'DatabaseConfig':
        """Create config for testing (no password required)."""
        return cls(
            host='localhost',
            port=5432,
            database='phoenix_test',
            user='test_user',
            password='test_pass',
            ssl_mode='disable',
            pool_min_connections=1,
            pool_max_connections=5
        )
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.database} "
            f"user={self.user} "
            f"password={self.password} "
            f"sslmode={self.ssl_mode}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (masks password)."""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password_set': bool(self.password),
            'ssl_mode': self.ssl_mode,
            'pool_min': self.pool_min_connections,
            'pool_max': self.pool_max_connections
        }


class MockConnection:
    """Mock database connection for testing."""
    
    def __init__(self):
        self._data = {}
    
    def cursor(self, cursor_factory=None):
        return MockCursor(self._data)
    
    def commit(self):
        pass
    
    def rollback(self):
        pass
    
    def set_isolation_level(self, level):
        pass


class MockCursor:
    """Mock database cursor for testing."""
    
    def __init__(self, data):
        self._data = data
        self._result = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def execute(self, query, params=None):
        # Simulate query execution
        if 'SELECT version()' in query:
            self._result = [{
                'version': 'PostgreSQL 15.0 (Mock)',
                'current_database': 'phoenix_test',
                'current_user': 'test_user'
            }]
        else:
            self._result = []
    
    def executemany(self, query, params_list):
        pass
    
    def fetchone(self):
        return self._result[0] if self._result else None
    
    def fetchall(self):
        return self._result or []


class MockPool:
    """Mock connection pool for testing."""
    
    def __init__(self, minconn, maxconn, dsn):
        self.minconn = minconn
        self.maxconn = maxconn
        self._connections = []
    
    def getconn(self):
        conn = MockConnection()
        self._connections.append(conn)
        return conn
    
    def putconn(self, conn):
        if conn in self._connections:
            self._connections.remove(conn)
    
    def closeall(self):
        self._connections.clear()


class ProductionDatabase:
    """Production-ready PostgreSQL database manager."""
    
    def __init__(self, config: DatabaseConfig, use_mock: bool = False):
        """Initialize production database with connection pooling."""
        self.config = config
        self.use_mock = use_mock or not PSYCOPG2_AVAILABLE
        self.pool = None
        
        # Performance metrics
        self.total_queries = 0
        self.total_query_time_ms = 0.0
        self.slow_queries = []
        
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Create connection pool."""
        if self.use_mock:
            self.pool = MockPool(
                self.config.pool_min_connections,
                self.config.pool_max_connections,
                self.config.get_connection_string()
            )
            logger.info("Mock database pool initialized")
            return
        
        try:
            self.pool = pool.SimpleConnectionPool(
                minconn=self.config.pool_min_connections,
                maxconn=self.config.pool_max_connections,
                dsn=self.config.get_connection_string()
            )
            logger.info(f"Database pool initialized: {self.config.pool_min_connections}-{self.config.pool_max_connections} connections")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self) -> Generator:
        """Get database connection from pool."""
        conn = None
        try:
            conn = self.pool.getconn()
            if hasattr(conn, 'set_isolation_level') and not self.use_mock:
                conn.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def execute_query(
        self,
        query: str,
        params: tuple = None,
        fetch_one: bool = False,
        fetch_all: bool = False
    ) -> Optional[Any]:
        """Execute SQL query with performance tracking."""
        start_time = time.perf_counter()
        
        with self.get_connection() as conn:
            cursor_factory = extras.RealDictCursor if not self.use_mock else None
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                cur.execute(query, params)
                
                query_time_ms = (time.perf_counter() - start_time) * 1000
                self.total_queries += 1
                self.total_query_time_ms += query_time_ms
                
                if query_time_ms > 100:
                    self.slow_queries.append({
                        'query': query[:200],
                        'time_ms': query_time_ms,
                        'timestamp': time.time()
                    })
                
                if fetch_one:
                    return cur.fetchone()
                elif fetch_all:
                    return cur.fetchall()
                return None
    
    def execute_many(self, query: str, params_list: list):
        """Execute query multiple times (batch insert)."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
    
    def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            result = self.execute_query(
                "SELECT version(), current_database(), current_user",
                fetch_one=True
            )
            return {
                'healthy': True,
                'version': result.get('version', 'Unknown') if result else 'Mock',
                'database': result.get('current_database', 'Unknown') if result else 'Mock',
                'user': result.get('current_user', 'Unknown') if result else 'Mock'
            }
        except Exception as e:
            return {'healthy': False, 'error': str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get query performance metrics."""
        avg_time = self.total_query_time_ms / max(1, self.total_queries)
        return {
            'total_queries': self.total_queries,
            'avg_query_time_ms': round(avg_time, 2),
            'slow_queries_count': len(self.slow_queries),
            'slow_queries_recent': self.slow_queries[-5:]
        }
    
    def close(self):
        """Close all connections."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database pool closed")


__all__ = ['DatabaseConfig', 'ProductionDatabase', 'PSYCOPG2_AVAILABLE']
