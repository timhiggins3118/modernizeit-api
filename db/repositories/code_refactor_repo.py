"""
Code Refactor Repository - MongoDB Implementation.

Stores Code Refactor artifacts in MongoDB.
Implements BaseArtifactRepository interface.

To switch to DynamoDB later:
1. Create code_refactor_repo_dynamodb.py implementing same interface
2. Update __init__.py to use DynamoDB implementation
3. No changes needed in runner or other calling code
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.repositories.base import BaseArtifactRepository
from db.mongodb import get_database

# Collection name
COLLECTION_NAME = "code_refactor"


class CodeRefactorRepository(BaseArtifactRepository):
    """
    MongoDB implementation of Code Refactor artifact storage.
    """

    async def _get_collection(self):
        """Get the MongoDB collection."""
        db = await get_database()
        return db[COLLECTION_NAME]

    async def save_artifact(
        self,
        account_id: str,
        application: str,
        program: str,
        artifact_type: str,
        job_id: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Save an artifact to MongoDB.

        Creates a document with metadata + raw data.
        """
        collection = await self._get_collection()

        document = {
            "account_id": account_id,
            "application": application,
            "program": program,
            "artifact_type": artifact_type,
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc),
            "data": data,
        }

        result = await collection.insert_one(document)
        return str(result.inserted_id)

    async def get_artifact(
        self,
        account_id: str,
        application: str,
        program: str,
        artifact_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific artifact (most recent if multiple exist).
        """
        collection = await self._get_collection()

        # Find most recent matching document
        cursor = collection.find({
            "account_id": account_id,
            "application": application,
            "program": program,
            "artifact_type": artifact_type,
        }).sort("created_at", -1).limit(1)

        docs = await cursor.to_list(length=1)
        if docs:
            doc = docs[0]
            doc["_id"] = str(doc["_id"])
            return doc
        return None

    async def get_artifacts(
        self,
        account_id: str,
        application: str,
        program: Optional[str] = None,
        artifact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query artifacts with optional filters.
        """
        collection = await self._get_collection()

        query = {
            "account_id": account_id,
            "application": application,
        }
        if program:
            query["program"] = program
        if artifact_type:
            query["artifact_type"] = artifact_type

        cursor = collection.find(query).sort("created_at", -1)
        docs = await cursor.to_list(length=None)

        # Convert ObjectId to string
        for doc in docs:
            doc["_id"] = str(doc["_id"])

        return docs

    async def delete_artifacts(
        self,
        account_id: str,
        application: str,
        program: Optional[str] = None
    ) -> int:
        """
        Delete artifacts.
        """
        collection = await self._get_collection()

        query = {
            "account_id": account_id,
            "application": application,
        }
        if program:
            query["program"] = program

        result = await collection.delete_many(query)
        return result.deleted_count

    async def list_programs(
        self,
        account_id: str,
        application: str
    ) -> List[str]:
        """
        List all programs that have artifacts.
        """
        collection = await self._get_collection()

        pipeline = [
            {"$match": {"account_id": account_id, "application": application}},
            {"$group": {"_id": "$program"}},
            {"$sort": {"_id": 1}}
        ]

        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        return [r["_id"] for r in results]

    async def list_artifact_types(
        self,
        account_id: str,
        application: str,
        program: str
    ) -> List[str]:
        """
        List all artifact types for a program.
        """
        collection = await self._get_collection()

        pipeline = [
            {"$match": {
                "account_id": account_id,
                "application": application,
                "program": program
            }},
            {"$group": {"_id": "$artifact_type"}},
            {"$sort": {"_id": 1}}
        ]

        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        return [r["_id"] for r in results]


# Synchronous client for use in non-async code (like runners)
# Uses pymongo directly instead of motor to avoid async/sync issues
from pymongo import MongoClient

_sync_client: Optional[MongoClient] = None


def _get_sync_client() -> MongoClient:
    """Get or create sync MongoDB client."""
    global _sync_client
    if _sync_client is None:
        from config.settings import settings
        _sync_client = MongoClient(settings.mongodb_uri)
    return _sync_client


def _get_sync_collection():
    """Get the code_refactor collection (sync)."""
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

    Uses pymongo directly (not motor) to avoid async/sync issues.
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
