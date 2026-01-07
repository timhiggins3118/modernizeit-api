"""
AWS credentials database module.

Stores ONE set of AWS credentials in SQLite.
Single row only - keeps it simple.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# Self-contained DB path logic (avoids circular import with jobs.py)
def _get_db_path() -> Path:
    """Get the path to the database file."""
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "jobs.db"


def _get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


@dataclass
class AWSCredentials:
    """AWS credentials record."""
    aws_access_key_id: str
    aws_secret_access_key: str
    region: str = "us-east-1"
    account_id: Optional[str] = None
    s3_bucket: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def init_aws_credentials_table() -> None:
    """Create the aws_credentials table if it doesn't exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aws_credentials (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                aws_access_key_id TEXT NOT NULL,
                aws_secret_access_key TEXT NOT NULL,
                region TEXT DEFAULT 'us-east-1',
                account_id TEXT,
                s3_bucket TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_credentials(creds: AWSCredentials) -> None:
    """
    Save AWS credentials. Overwrites any existing credentials.
    Only one set of credentials allowed.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Delete any existing and insert new (single row, id=1)
        cursor.execute("DELETE FROM aws_credentials")
        cursor.execute("""
            INSERT INTO aws_credentials
            (id, aws_access_key_id, aws_secret_access_key, region, account_id, s3_bucket)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            creds.aws_access_key_id,
            creds.aws_secret_access_key,
            creds.region,
            creds.account_id,
            creds.s3_bucket
        ))
        conn.commit()
    finally:
        conn.close()


def get_credentials() -> Optional[AWSCredentials]:
    """
    Get the AWS credentials.

    Returns:
        AWSCredentials if set, None otherwise
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT aws_access_key_id, aws_secret_access_key,
                   region, account_id, s3_bucket, created_at, updated_at
            FROM aws_credentials
            WHERE id = 1
        """)
        row = cursor.fetchone()
        if row is None:
            return None
        return AWSCredentials(
            aws_access_key_id=row[0],
            aws_secret_access_key=row[1],
            region=row[2],
            account_id=row[3],
            s3_bucket=row[4],
            created_at=datetime.fromisoformat(row[5]) if row[5] else None,
            updated_at=datetime.fromisoformat(row[6]) if row[6] else None
        )
    finally:
        conn.close()


def delete_credentials() -> bool:
    """
    Delete the AWS credentials.

    Returns:
        True if deleted, False if nothing to delete
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM aws_credentials")
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
