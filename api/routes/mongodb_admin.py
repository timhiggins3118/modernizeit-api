"""
MongoDB Admin Routes

Endpoints for importing existing JSON files and managing MongoDB collections.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from db.mongodb import (
    get_database,
    store_code_analysis_artifact,
    get_code_analysis_artifacts,
)


router = APIRouter(prefix="/mongodb", tags=["mongodb_admin"])


class ImportRequest(BaseModel):
    """Request to import existing JSON files to MongoDB."""
    account_id: str
    application: str
    program: Optional[str] = None  # If not provided, imports all programs


class ImportResponse(BaseModel):
    """Response from import operation."""
    success: bool
    imported_count: int
    artifacts: list[str]
    errors: list[str]


@router.post(
    "/import/code-analysis",
    response_model=ImportResponse,
    summary="Import Code Analysis JSON to MongoDB",
    description="""
    Import existing Code Analysis JSON files into MongoDB.

    Looks in the standard output path:
    {base_local_path}/code-transformation-v2/{account_id}/{application}/code_analysis/reports/

    Imports all JSON files found (summary, line_inventory, procedure_model, etc.)
    """
)
async def import_code_analysis(request: ImportRequest) -> ImportResponse:
    """Import existing Code Analysis JSON files to MongoDB."""

    # Build path to reports folder
    reports_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / request.account_id
        / request.application
        / "code_analysis"
        / "reports"
    )

    if not reports_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Reports folder not found: {reports_path}"
        )

    imported = []
    errors = []

    # Find all JSON files
    json_files = list(reports_path.glob("*.json"))

    if not json_files:
        raise HTTPException(
            status_code=404,
            detail=f"No JSON files found in: {reports_path}"
        )

    for json_file in json_files:
        try:
            # Parse filename to extract program and artifact type
            # Examples: ifpr321_summary.json, ifpr321_line_inventory.json, cross_reference.json
            filename = json_file.stem  # without extension

            # Determine program and artifact type
            if "_" in filename:
                parts = filename.rsplit("_", 1)
                if len(parts) == 2 and parts[0].lower() not in ["cross", "comprehensive", "unified"]:
                    program = parts[0].upper()
                    artifact_type = parts[1]
                else:
                    # App-wide artifact
                    program = "_application"
                    artifact_type = filename
            else:
                program = "_application"
                artifact_type = filename

            # Filter by program if specified
            if request.program and program != request.program.upper():
                continue

            # Load JSON data
            with open(json_file, "r") as f:
                data = json.load(f)

            # Store in MongoDB
            job_id = f"import_{request.account_id}_{request.application}"
            doc_id = await store_code_analysis_artifact(
                account_id=request.account_id,
                application=request.application,
                program=program,
                artifact_type=artifact_type,
                job_id=job_id,
                data=data
            )

            imported.append(f"{program}/{artifact_type} -> {doc_id}")

        except Exception as e:
            errors.append(f"{json_file.name}: {str(e)}")

    return ImportResponse(
        success=len(errors) == 0,
        imported_count=len(imported),
        artifacts=imported,
        errors=errors
    )


@router.get(
    "/code-analysis/{account_id}/{application}",
    summary="List Code Analysis artifacts in MongoDB",
    description="List all Code Analysis artifacts stored in MongoDB for an application."
)
async def list_code_analysis_artifacts(
    account_id: str,
    application: str,
    program: Optional[str] = None,
    artifact_type: Optional[str] = None
):
    """List Code Analysis artifacts from MongoDB."""

    artifacts = await get_code_analysis_artifacts(
        account_id=account_id,
        application=application,
        program=program,
        artifact_type=artifact_type
    )

    # Convert ObjectId to string for JSON response
    result = []
    for doc in artifacts:
        result.append({
            "_id": str(doc["_id"]),
            "account_id": doc["account_id"],
            "application": doc["application"],
            "program": doc["program"],
            "artifact_type": doc["artifact_type"],
            "job_id": doc["job_id"],
            # Don't include full data in list, just summary
            "data_keys": list(doc["data"].keys()) if isinstance(doc["data"], dict) else "array",
        })

    return {
        "count": len(result),
        "artifacts": result
    }


@router.get(
    "/code-analysis/{account_id}/{application}/{program}/{artifact_type}",
    summary="Get specific Code Analysis artifact",
    description="Get a specific Code Analysis artifact from MongoDB."
)
async def get_code_analysis_artifact(
    account_id: str,
    application: str,
    program: str,
    artifact_type: str
):
    """Get a specific Code Analysis artifact from MongoDB."""

    artifacts = await get_code_analysis_artifacts(
        account_id=account_id,
        application=application,
        program=program,
        artifact_type=artifact_type
    )

    if not artifacts:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {program}/{artifact_type}"
        )

    # Return the most recent one (last in list)
    doc = artifacts[-1]

    return {
        "_id": str(doc["_id"]),
        "account_id": doc["account_id"],
        "application": doc["application"],
        "program": doc["program"],
        "artifact_type": doc["artifact_type"],
        "job_id": doc["job_id"],
        "data": doc["data"],  # Full data
    }


@router.get(
    "/code-refactor/{account_id}/{application}",
    summary="List Code Refactor artifacts in MongoDB",
    description="List all Code Refactor artifacts stored in MongoDB for an application."
)
async def list_code_refactor_artifacts(
    account_id: str,
    application: str,
    program: Optional[str] = None,
    artifact_type: Optional[str] = None
):
    """List Code Refactor artifacts from MongoDB."""
    db = await get_database()
    collection = db["code_refactor"]

    query = {
        "account_id": account_id,
        "application": application,
    }
    if program:
        query["program"] = program
    if artifact_type:
        query["artifact_type"] = artifact_type

    cursor = collection.find(query).sort("created_at", -1)
    artifacts = await cursor.to_list(length=None)

    # Convert for JSON response
    result = []
    for doc in artifacts:
        result.append({
            "_id": str(doc["_id"]),
            "account_id": doc["account_id"],
            "application": doc["application"],
            "program": doc["program"],
            "artifact_type": doc["artifact_type"],
            "job_id": doc["job_id"],
            "data_keys": list(doc["data"].keys()) if isinstance(doc["data"], dict) else "array",
        })

    return {
        "count": len(result),
        "artifacts": result
    }


@router.get(
    "/code-refactor/{account_id}/{application}/{program}/{artifact_type}",
    summary="Get specific Code Refactor artifact",
    description="Get a specific Code Refactor artifact from MongoDB."
)
async def get_code_refactor_artifact(
    account_id: str,
    application: str,
    program: str,
    artifact_type: str
):
    """Get a specific Code Refactor artifact from MongoDB."""
    db = await get_database()
    collection = db["code_refactor"]

    cursor = collection.find({
        "account_id": account_id,
        "application": application,
        "program": program,
        "artifact_type": artifact_type,
    }).sort("created_at", -1).limit(1)

    artifacts = await cursor.to_list(length=1)

    if not artifacts:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {program}/{artifact_type}"
        )

    doc = artifacts[0]

    return {
        "_id": str(doc["_id"]),
        "account_id": doc["account_id"],
        "application": doc["application"],
        "program": doc["program"],
        "artifact_type": doc["artifact_type"],
        "job_id": doc["job_id"],
        "data": doc["data"],
    }


@router.get(
    "/status",
    summary="MongoDB connection status",
    description="Check MongoDB connection and list collections."
)
async def mongodb_status():
    """Check MongoDB connection status."""
    try:
        db = await get_database()
        collections = await db.list_collection_names()

        # Get document counts
        counts = {}
        for coll_name in collections:
            coll = db[coll_name]
            counts[coll_name] = await coll.count_documents({})

        return {
            "status": "connected",
            "database": settings.mongodb_database,
            "collections": collections,
            "document_counts": counts
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@router.delete(
    "/reset",
    summary="Reset all MongoDB collections",
    description="Delete all documents from all collections. Use with caution."
)
async def reset_mongodb():
    """Clear all documents from all MongoDB collections."""
    try:
        db = await get_database()
        collections = await db.list_collection_names()

        results = {}
        total_deleted = 0

        for coll_name in collections:
            coll = db[coll_name]
            count_before = await coll.count_documents({})
            await coll.delete_many({})
            results[coll_name] = count_before
            total_deleted += count_before

        return {
            "success": True,
            "message": f"Deleted {total_deleted} documents from {len(collections)} collections",
            "deleted_counts": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/reset/{collection_name}",
    summary="Reset specific MongoDB collection",
    description="Delete all documents from a specific collection."
)
async def reset_mongodb_collection(collection_name: str):
    """Clear all documents from a specific MongoDB collection."""
    try:
        db = await get_database()
        collections = await db.list_collection_names()

        if collection_name not in collections:
            raise HTTPException(
                status_code=404,
                detail=f"Collection not found: {collection_name}. Available: {collections}"
            )

        coll = db[collection_name]
        count_before = await coll.count_documents({})
        await coll.delete_many({})

        return {
            "success": True,
            "collection": collection_name,
            "deleted_count": count_before
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/reset-jobs",
    summary="Reset SQLite jobs database",
    description="Delete all job records from SQLite."
)
async def reset_sqlite_jobs():
    """Clear all jobs from SQLite database."""
    import sqlite3
    from db.jobs import _get_db_path

    try:
        db_path = _get_db_path()

        if not db_path.exists():
            return {
                "success": True,
                "message": "No database file found - already clean",
                "deleted_count": 0
            }

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count before delete
        cursor.execute("SELECT COUNT(*) FROM jobs")
        count = cursor.fetchone()[0]

        # Delete all
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"Deleted {count} job records",
            "deleted_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/reset-all",
    summary="Reset all databases",
    description="Delete all data from MongoDB and SQLite. Use with caution."
)
async def reset_all_databases():
    """Clear all data from MongoDB and SQLite."""
    import sqlite3
    from db.jobs import _get_db_path

    results = {
        "mongodb": {},
        "sqlite": {}
    }

    # MongoDB
    try:
        db = await get_database()
        collections = await db.list_collection_names()
        mongo_total = 0

        for coll_name in collections:
            coll = db[coll_name]
            count = await coll.count_documents({})
            await coll.delete_many({})
            results["mongodb"][coll_name] = count
            mongo_total += count

        results["mongodb"]["_total"] = mongo_total
    except Exception as e:
        results["mongodb"]["_error"] = str(e)

    # SQLite
    try:
        db_path = _get_db_path()
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM jobs")
            conn.commit()
            conn.close()
            results["sqlite"]["jobs"] = count
        else:
            results["sqlite"]["jobs"] = 0
    except Exception as e:
        results["sqlite"]["_error"] = str(e)

    return {
        "success": True,
        "results": results
    }
