"""Phoenix Guardian API Package.

FastAPI-based REST API layer for the Phoenix Guardian medical AI system.

This package provides:
- REST endpoints for encounter processing
- JWT authentication
- Multi-agent orchestration
- HIPAA-compliant logging
"""

from phoenix_guardian.api.main import app

__all__ = ["app"]
