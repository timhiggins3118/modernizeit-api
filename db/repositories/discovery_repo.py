"""
Discovery Repository - MongoDB Implementation.

Stores Discovery artifacts in MongoDB.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

COLLECTION_NAME = "discovery"

_sync_client: Optional[MongoClient] = None


def _get_sync_client() -> MongoClient:
    """Get or create sync MongoDB client."""
    global _sync_client
    if _sync_client is None:
        from config.settings import settings
        _sync_client = MongoClient(settings.mongodb_uri)
    return _sync_client


def _get_sync_collection():
    """Get the collection (sync)."""
    from config.settings import settings
    client = _get_sync_client()
    db = client[settings.mongodb_database]
    return db[COLLECTION_NAME]


def save_artifact_sync(
    account_id: str,
    application: str,
    program: str,
    artifact_type: str,
    job_id: str,
    data: Dict[str, Any]
) -> str:
    """
    Synchronous save for use in non-async code like runners.
    """
    collection = _get_sync_collection()

    document = {
        "account_id": account_id,
        "application": application,
        "program": program,
        "artifact_type": artifact_type,
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc),
        "data": data,
    }

    result = collection.insert_one(document)
    return str(result.inserted_id)
