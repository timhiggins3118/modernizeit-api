"""
MongoDB connection manager for ModernizeIT API.

Uses Motor (async MongoDB driver) for FastAPI compatibility.
Stores raw JSON artifacts from all flows.
"""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure

from config.settings import settings


# Global client instance (initialized on first use)
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def get_mongodb_client() -> AsyncIOMotorClient:
    """
    Get or create the MongoDB client.

    Uses settings.mongodb_uri for connection string.
    Supports both local MongoDB and Atlas.

    Returns:
        AsyncIOMotorClient instance
    """
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        # Test connection
        try:
            await _client.admin.command('ping')
            print(f"[mongodb] Connected to MongoDB")
        except ConnectionFailure as e:
            print(f"[mongodb] Connection failed: {e}")
            raise
    return _client


async def get_database() -> AsyncIOMotorDatabase:
    """
    Get the ModernizeIT database.

    Returns:
        AsyncIOMotorDatabase for the configured database name
    """
    global _db
    if _db is None:
        client = await get_mongodb_client()
        _db = client[settings.mongodb_database]
    return _db


async def close_mongodb():
    """Close the MongoDB connection."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        print("[mongodb] Connection closed")


# Collection names for Code Analysis
COLLECTION_CODE_ANALYSIS = "code_analysis"


async def get_code_analysis_collection():
    """Get the code_analysis collection."""
    db = await get_database()
    return db[COLLECTION_CODE_ANALYSIS]


async def store_code_analysis_artifact(
    account_id: str,
    application: str,
    program: str,
    artifact_type: str,
    job_id: str,
    data: dict
) -> str:
    """
    Store a code analysis artifact in MongoDB.

    Args:
        account_id: Customer account ID (e.g., "EVH")
        application: Application name (e.g., "TestApp01")
        program: Program name (e.g., "IFPR321")
        artifact_type: Type of artifact (e.g., "summary", "line_inventory", "procedure_model")
        job_id: Job ID that generated this artifact
        data: Raw JSON data to store

    Returns:
        Inserted document ID as string
    """
    collection = await get_code_analysis_collection()

    document = {
        "account_id": account_id,
        "application": application,
        "program": program,
        "artifact_type": artifact_type,
        "job_id": job_id,
        "data": data,  # Raw JSON stored as-is
    }

    result = await collection.insert_one(document)
    return str(result.inserted_id)


async def get_code_analysis_artifacts(
    account_id: str,
    application: str,
    program: Optional[str] = None,
    artifact_type: Optional[str] = None
) -> list:
    """
    Query code analysis artifacts.

    Args:
        account_id: Customer account ID
        application: Application name
        program: Optional program filter
        artifact_type: Optional artifact type filter

    Returns:
        List of matching documents
    """
    collection = await get_code_analysis_collection()

    query = {
        "account_id": account_id,
        "application": application,
    }
    if program:
        query["program"] = program
    if artifact_type:
        query["artifact_type"] = artifact_type

    cursor = collection.find(query)
    return await cursor.to_list(length=None)
