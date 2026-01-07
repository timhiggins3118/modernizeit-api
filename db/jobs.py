"""
Job tracking database module.

Provides lightweight job tracking using sqlite3.
Database file is stored at settings.base_local_path / "jobs.db".
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import json

from config.settings import settings


@dataclass
class JobRecord:
    """
    Job record dataclass.

    Stores metadata about a job execution.
    """
    job_id: str
    flow_type: str  # e.g. "ingest"
    status: str  # "running", "completed", "failed"
    created_at: datetime
    updated_at: datetime
    artifacts_path: str  # Absolute path to the job's artifacts root
    input_json: str  # JSON string of original request


def _get_db_path() -> Path:
    """Get the path to the jobs database file."""
    # Database lives in data/ folder (not in output folder which gets deleted)
    from config.settings import PROJECT_ROOT
    return PROJECT_ROOT / "data" / "jobs.db"


def _get_connection() -> sqlite3.Connection:
    """
    Get a database connection.

    Creates the base_local_path directory if it doesn't exist.
    """
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def init_db() -> None:
    """
    Initialize the database.

    Creates the jobs table if it doesn't exist.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                flow_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                artifacts_path TEXT NOT NULL,
                input_json TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_job(record: JobRecord) -> None:
    """
    Save a job record to the database.

    Inserts or replaces by job_id.

    Args:
        record: JobRecord to save
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO jobs
            (job_id, flow_type, status, created_at, updated_at, artifacts_path, input_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record.job_id,
            record.flow_type,
            record.status,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
            record.artifacts_path,
            record.input_json
        ))
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[JobRecord]:
    """
    Fetch a job record by job_id.

    Args:
        job_id: The job identifier to look up

    Returns:
        JobRecord if found, None otherwise
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT job_id, flow_type, status, created_at, updated_at, artifacts_path, input_json
            FROM jobs
            WHERE job_id = ?
        """, (job_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return JobRecord(
            job_id=row[0],
            flow_type=row[1],
            status=row[2],
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            artifacts_path=row[5],
            input_json=row[6]
        )
    finally:
        conn.close()


def list_jobs(
    account_id: Optional[str] = None,
    application_name: Optional[str] = None,
    flow_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[JobRecord]:
    """
    List job records with optional filters.

    Args:
        account_id: Filter by account ID (extracted from input_json)
        application_name: Filter by application name (extracted from input_json)
        flow_type: Filter by flow type (codeanalysis, dependencymapper, etc.)
        status: Filter by status (completed, running, failed)
        limit: Maximum number of records to return

    Returns:
        List of JobRecord objects matching the filters
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Build query with filters
        query = "SELECT job_id, flow_type, status, created_at, updated_at, artifacts_path, input_json FROM jobs WHERE 1=1"
        params = []

        if flow_type:
            query += " AND flow_type = ?"
            params.append(flow_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        # For account_id and application_name, we filter in Python since they're in JSON
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit * 10 if (account_id or application_name) else limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            record = JobRecord(
                job_id=row[0],
                flow_type=row[1],
                status=row[2],
                created_at=datetime.fromisoformat(row[3]),
                updated_at=datetime.fromisoformat(row[4]),
                artifacts_path=row[5],
                input_json=row[6]
            )

            # Filter by account_id and application_name if specified
            if account_id or application_name:
                try:
                    input_data = json.loads(record.input_json)
                    record_account = input_data.get('scout_account_id', '')
                    record_app = input_data.get('application_name', '')

                    if account_id and record_account != account_id:
                        continue
                    if application_name and record_app != application_name:
                        continue
                except json.JSONDecodeError:
                    continue

            results.append(record)
            if len(results) >= limit:
                break

        return results
    finally:
        conn.close()
