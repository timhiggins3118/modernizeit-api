"""
API Routes module

Re-exports all API routers.
"""

from api.routes.ingest import router as ingest_router

__all__ = [
    'ingest_router',
]
