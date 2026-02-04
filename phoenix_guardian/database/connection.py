"""
Database connection management for Phoenix Guardian.

Provides:
- Connection pooling with QueuePool
- Session management with context managers
- FastAPI dependency injection
- Health checks
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from phoenix_guardian.models import Base


class DatabaseConfig:
    """Database configuration from environment."""

    def __init__(self) -> None:
        """Load database configuration from environment."""
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.name = os.getenv("DB_NAME", "phoenix_guardian")
        self.user = os.getenv("DB_USER", "phoenix")
        self.password = os.getenv("DB_PASSWORD", "")
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.echo = os.getenv("DB_ECHO", "false").lower() == "true"

    @property
    def url(self) -> str:
        """Build PostgreSQL connection URL.

        Returns:
            PostgreSQL connection URL
        """
        return (
            f"postgresql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.name}"
        )

    @property
    def async_url(self) -> str:
        """Build async PostgreSQL connection URL.

        Returns:
            Async PostgreSQL connection URL (for asyncpg)
        """
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.name}"
        )


class Database:
    """
    Database connection manager.

    Handles connection pooling, session management,
    and database initialization.

    Usage:
        db = Database()
        db.connect()

        with db.session_scope() as session:
            user = session.query(User).first()

        db.disconnect()
    """

    _instance: Optional["Database"] = None

    def __new__(cls) -> "Database":
        """Singleton pattern for database instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize database manager."""
        if getattr(self, "_initialized", False):
            return

        self.config = DatabaseConfig()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._initialized = True

    @property
    def engine(self) -> Engine:
        """Get database engine.

        Returns:
            SQLAlchemy engine

        Raises:
            RuntimeError: If not connected
        """
        if self._engine is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get session factory.

        Returns:
            SQLAlchemy session factory

        Raises:
            RuntimeError: If not connected
        """
        if self._session_factory is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._session_factory

    def connect(self, url: Optional[str] = None) -> None:
        """
        Connect to database.

        Args:
            url: Optional database URL (uses config if not provided)
        """
        if self._engine is not None:
            return  # Already connected

        connection_url = url or self.config.url

        self._engine = create_engine(
            connection_url,
            poolclass=QueuePool,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_pre_ping=True,  # Check connections before using
            echo=self.config.echo,
        )

        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    def disconnect(self) -> None:
        """Disconnect from database."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def create_tables(self) -> None:
        """Create all database tables.

        Uses SQLAlchemy metadata to create tables.
        Safe to call multiple times (won't recreate existing tables).
        """
        Base.metadata.create_all(self.engine)

    def drop_tables(self) -> None:
        """Drop all database tables.

        WARNING: This will delete all data!
        Use only for testing or development.
        """
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around operations.

        Usage:
            with db.session_scope() as session:
                user = User(email="test@example.com")
                session.add(user)

        Automatically commits on success, rolls back on error.
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """
        Get a new session.

        Caller is responsible for closing the session.

        Returns:
            New SQLAlchemy session
        """
        return self.session_factory()

    def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            True if database is reachable
        """
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# Global database instance
db = Database()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    Yields:
        Database session
    """
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()


def init_db(url: Optional[str] = None) -> Database:
    """
    Initialize database connection.

    Args:
        url: Optional database URL

    Returns:
        Database instance
    """
    db.connect(url)
    return db


def get_test_db_url() -> str:
    """
    Get test database URL (in-memory SQLite).

    Returns:
        SQLite in-memory database URL
    """
    return "sqlite:///:memory:"
