"""
Saved flows database module.

Provides storage and retrieval of saved workflow configurations.
Database file is stored at PROJECT_ROOT / "data" / "jobs.db" (shares jobs database).
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import json

from config.settings import settings


@dataclass
class SavedFlowRecord:
    """
    Saved flow record dataclass.

    Stores a complete workflow configuration including:
    - ReactFlow canvas state (nodes, edges)
    - Job IDs associated with each node
    - Account/application context
    """
    id: str
    name: str
    account_id: str
    application_name: str
    flow_data: str  # JSON string of ReactFlow state
    job_mappings: str  # JSON string of {node_id: job_id}
    created_at: datetime
    updated_at: datetime


def _get_db_path() -> Path:
    """Get the path to the database file (shared with jobs)."""
    from config.settings import PROJECT_ROOT
    return PROJECT_ROOT / "data" / "jobs.db"


def _get_connection() -> sqlite3.Connection:
    """
    Get a database connection.

    Creates the data directory if it doesn't exist.
    """
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def init_db() -> None:
    """
    Initialize the database.

    Creates the saved_flows table if it doesn't exist.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_flows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                account_id TEXT NOT NULL,
                application_name TEXT NOT NULL,
                flow_data TEXT NOT NULL,
                job_mappings TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_flow(record: SavedFlowRecord) -> None:
    """
    Save a flow record to the database.

    Inserts or replaces by id.

    Args:
        record: SavedFlowRecord to save
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO saved_flows
            (id, name, account_id, application_name, flow_data, job_mappings, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.id,
            record.name,
            record.account_id,
            record.application_name,
            record.flow_data,
            record.job_mappings,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def get_flow(flow_id: str) -> Optional[SavedFlowRecord]:
    """
    Get a saved flow by ID.

    Args:
        flow_id: Flow ID to retrieve

    Returns:
        SavedFlowRecord if found, None otherwise
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, account_id, application_name, flow_data, job_mappings, created_at, updated_at
            FROM saved_flows
            WHERE id = ?
        """, (flow_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return SavedFlowRecord(
            id=row[0],
            name=row[1],
            account_id=row[2],
            application_name=row[3],
            flow_data=row[4],
            job_mappings=row[5] or "{}",
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7]),
        )
    finally:
        conn.close()


def list_flows(account_id: Optional[str] = None) -> List[SavedFlowRecord]:
    """
    List all saved flows, optionally filtered by account.

    Args:
        account_id: Optional account ID filter

    Returns:
        List of SavedFlowRecord objects, ordered by updated_at DESC
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        if account_id:
            cursor.execute("""
                SELECT id, name, account_id, application_name, flow_data, job_mappings, created_at, updated_at
                FROM saved_flows
                WHERE account_id = ?
                ORDER BY updated_at DESC
            """, (account_id,))
        else:
            cursor.execute("""
                SELECT id, name, account_id, application_name, flow_data, job_mappings, created_at, updated_at
                FROM saved_flows
                ORDER BY updated_at DESC
            """)

        rows = cursor.fetchall()
        return [
            SavedFlowRecord(
                id=row[0],
                name=row[1],
                account_id=row[2],
                application_name=row[3],
                flow_data=row[4],
                job_mappings=row[5] or "{}",
                created_at=datetime.fromisoformat(row[6]),
                updated_at=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def delete_flow(flow_id: str) -> bool:
    """
    Delete a saved flow by ID.

    Args:
        flow_id: Flow ID to delete

    Returns:
        True if deleted, False if not found
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_flows WHERE id = ?", (flow_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_flow_name(flow_id: str, new_name: str) -> bool:
    """
    Update a flow's name.

    Args:
        flow_id: Flow ID to update
        new_name: New flow name

    Returns:
        True if updated, False if not found
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE saved_flows
            SET name = ?, updated_at = ?
            WHERE id = ?
        """, (new_name, datetime.now().isoformat(), flow_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
