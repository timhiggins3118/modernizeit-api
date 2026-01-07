"""
Accounts database module.

Stores account configuration with S3 settings in SQLite.
Multi-tenant: each account has its own S3 bucket/region/prefix.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List


# Self-contained DB path logic (avoids circular import)
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
class Account:
    """Account record with S3 configuration."""
    account_id: str
    name: str
    description: Optional[str] = None
    is_default: bool = False
    # Storage Configuration
    storage_type: str = "s3"  # 's3' or 'local'
    # S3 Storage Configuration (used when storage_type = 's3')
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_prefix: str = ""
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def init_accounts_table() -> None:
    """Create the accounts table if it doesn't exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                is_default INTEGER DEFAULT 0,
                s3_bucket TEXT,
                s3_region TEXT DEFAULT 'us-east-1',
                s3_prefix TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_account(account: Account) -> Account:
    """
    Save or update an account.
    Uses upsert - inserts if new, updates if exists.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # SQLite upsert
        cursor.execute("""
            INSERT INTO accounts
            (account_id, name, description, is_default, storage_type, s3_bucket, s3_region, s3_prefix, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(account_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                is_default = excluded.is_default,
                storage_type = excluded.storage_type,
                s3_bucket = excluded.s3_bucket,
                s3_region = excluded.s3_region,
                s3_prefix = excluded.s3_prefix,
                updated_at = CURRENT_TIMESTAMP
        """, (
            account.account_id,
            account.name,
            account.description,
            1 if account.is_default else 0,
            account.storage_type,
            account.s3_bucket,
            account.s3_region,
            account.s3_prefix
        ))
        conn.commit()
        return get_account(account.account_id)
    finally:
        conn.close()


def get_account(account_id: str) -> Optional[Account]:
    """
    Get an account by ID.

    Args:
        account_id: The account ID (e.g., "0U812")

    Returns:
        Account if found, None otherwise
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT account_id, name, description, is_default, storage_type,
                   s3_bucket, s3_region, s3_prefix, created_at, updated_at
            FROM accounts
            WHERE account_id = ?
        """, (account_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return Account(
            account_id=row[0],
            name=row[1],
            description=row[2],
            is_default=bool(row[3]),
            storage_type=row[4] or "s3",
            s3_bucket=row[5],
            s3_region=row[6] or "us-east-1",
            s3_prefix=row[7] or "",
            created_at=datetime.fromisoformat(row[8]) if row[8] else None,
            updated_at=datetime.fromisoformat(row[9]) if row[9] else None
        )
    finally:
        conn.close()


def get_all_accounts() -> List[Account]:
    """
    Get all accounts.

    Returns:
        List of all accounts
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT account_id, name, description, is_default, storage_type,
                   s3_bucket, s3_region, s3_prefix, created_at, updated_at
            FROM accounts
            ORDER BY name
        """)
        rows = cursor.fetchall()
        return [
            Account(
                account_id=row[0],
                name=row[1],
                description=row[2],
                is_default=bool(row[3]),
                storage_type=row[4] or "s3",
                s3_bucket=row[5],
                s3_region=row[6] or "us-east-1",
                s3_prefix=row[7] or "",
                created_at=datetime.fromisoformat(row[8]) if row[8] else None,
                updated_at=datetime.fromisoformat(row[9]) if row[9] else None
            )
            for row in rows
        ]
    finally:
        conn.close()


def delete_account(account_id: str) -> bool:
    """
    Delete an account by ID.

    Args:
        account_id: The account ID to delete

    Returns:
        True if deleted, False if not found
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_account_s3_config(account_id: str) -> Optional[dict]:
    """
    Get S3 configuration for an account.

    Args:
        account_id: The account ID

    Returns:
        Dict with storage_type, s3_bucket, s3_region, s3_prefix or None if not found
    """
    account = get_account(account_id)
    if account is None:
        return None
    return {
        "storage_type": account.storage_type,
        "s3_bucket": account.s3_bucket,
        "s3_region": account.s3_region,
        "s3_prefix": account.s3_prefix
    }
