"""
Local Data Provider - SQLite implementation that mimics DynamoDB.

This provider stores data in SQLite with the EXACT same schema as DynamoDB,
allowing seamless migration between local and cloud storage.

Use this for:
  - Local development/testing
  - Offline mode
  - Desktop app deployment

Created: January 1, 2026
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.base_provider import BaseDataProvider
from db.models import Application, FileRecord, PortfolioSummary


def _get_db_path() -> Path:
    """Get the path to the local database file."""
    project_root = Path(__file__).resolve().parent.parent
    db_dir = project_root / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "local_provider.db"


def _now_iso() -> str:
    """Get current time in ISO 8601 format (matching DynamoDB)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_app_id(name: str) -> str:
    """Generate application ID matching DynamoDB pattern."""
    timestamp = int(time.time())
    return f"app_{name}_{timestamp}"


def _generate_file_id(app_id: str) -> str:
    """Generate file ID matching DynamoDB pattern."""
    timestamp = int(time.time() * 1000000)  # Include microseconds
    return f"file_{app_id}_{timestamp}"


class LocalProvider(BaseDataProvider):
    """
    SQLite implementation of the data provider.

    Mimics DynamoDB schema exactly for migration compatibility.

    Usage:
        provider = LocalProvider(account_id="341")
        apps = provider.list_applications()
    """

    def __init__(self, account_id: str, db_path: Optional[Path] = None):
        """
        Initialize the local provider.

        Args:
            account_id: Account ID (for compatibility with DynamoDB pattern)
            db_path: Optional custom database path
        """
        self.account_id = account_id
        self.db_path = db_path or _get_db_path()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Return dicts instead of tuples
        return conn

    def _init_database(self):
        """Initialize database tables matching DynamoDB schema."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Applications table - matches DynamoDB schema exactly
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    application_id TEXT PRIMARY KEY,
                    application_name TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    file_count TEXT DEFAULT '0',
                    created_at TEXT,
                    updated_at TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)

            # Files table - matches DynamoDB schema exactly
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT DEFAULT 'cobol',
                    file_size TEXT DEFAULT '0',
                    status TEXT DEFAULT 'uploaded',
                    analysis_status TEXT DEFAULT '',
                    s3_path TEXT DEFAULT '',
                    local_path TEXT DEFAULT '',
                    uploaded_at TEXT,
                    updated_at TEXT,
                    version TEXT DEFAULT '1',

                    -- Job tracking fields (matching DynamoDB)
                    cobol_job_id TEXT DEFAULT '',
                    refactor_job_id TEXT DEFAULT '',
                    dependency_job_id TEXT DEFAULT '',
                    monolith_job_id TEXT DEFAULT '',
                    data_job_id TEXT DEFAULT '',
                    discovery_job_id TEXT DEFAULT '',
                    architecture_job_id TEXT DEFAULT '',
                    jgv3_generation_job_id TEXT DEFAULT '',
                    jgv3_status TEXT DEFAULT '',
                    jgv3_flow_status TEXT DEFAULT '',
                    jgv3_workflow_status TEXT DEFAULT '',

                    FOREIGN KEY (application_id) REFERENCES applications(application_id)
                )
            """)

            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_apps_account ON applications(account_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_account ON files(account_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_app ON files(application_id)")

            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # CONNECTION / STATUS
    # =========================================================================

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to SQLite."""
        result = {
            "connected": False,
            "provider": "local",
            "account_id": self.account_id,
            "db_path": str(self.db_path),
            "tables": {}
        }

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Count applications
            cursor.execute(
                "SELECT COUNT(*) FROM applications WHERE account_id = ?",
                (self.account_id,)
            )
            apps_count = cursor.fetchone()[0]
            result["tables"]["applications"] = {"count": apps_count}

            # Count files
            cursor.execute(
                "SELECT COUNT(*) FROM files WHERE account_id = ?",
                (self.account_id,)
            )
            files_count = cursor.fetchone()[0]
            result["tables"]["files"] = {"count": files_count}

            conn.close()
            result["connected"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider metadata."""
        return {
            "provider": "local",
            "version": "1.0.0",
            "account_id": self.account_id,
            "db_path": str(self.db_path),
            "capabilities": {
                "read": True,
                "write": True,
                "delete": True
            }
        }

    # =========================================================================
    # APPLICATIONS - READ
    # =========================================================================

    def list_applications(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Application]:
        """List all applications for this account."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM applications WHERE account_id = ? ORDER BY updated_at DESC"
            params = [self.account_id]

            if limit:
                query += " LIMIT ?"
                params.append(limit)
            if offset:
                query += " OFFSET ?"
                params.append(offset)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_application(dict(row)) for row in rows]
        finally:
            conn.close()

    def get_application(self, application_id: str) -> Optional[Application]:
        """Get a single application by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM applications WHERE application_id = ?",
                (application_id,)
            )
            row = cursor.fetchone()
            return self._row_to_application(dict(row)) if row else None
        finally:
            conn.close()

    def find_application_by_name(self, name: str) -> Optional[Application]:
        """Find application by name."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM applications WHERE application_name = ? AND account_id = ?",
                (name, self.account_id)
            )
            row = cursor.fetchone()
            return self._row_to_application(dict(row)) if row else None
        finally:
            conn.close()

    def _row_to_application(self, row: Dict[str, Any]) -> Application:
        """Convert SQLite row to Application model."""
        # Parse metadata JSON
        metadata = {}
        if row.get('metadata'):
            try:
                metadata = json.loads(row['metadata'])
            except:
                pass

        return Application(
            application_id=row['application_id'],
            application_name=row['application_name'],
            account_id=row['account_id'],
            status=row.get('status', 'active'),
            progress=0,  # Calculate from files if needed
            file_count=int(row.get('file_count', 0) or 0),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            metadata=metadata
        )

    # =========================================================================
    # APPLICATIONS - WRITE
    # =========================================================================

    def create_application(self, application: Application) -> str:
        """Create a new application."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Generate ID if not provided
            app_id = application.application_id or _generate_app_id(application.application_name)
            now = _now_iso()

            cursor.execute("""
                INSERT INTO applications
                (application_id, application_name, account_id, status, file_count,
                 created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app_id,
                application.application_name,
                self.account_id,
                application.status or 'active',
                str(application.file_count or 0),
                now,
                now,
                json.dumps(application.metadata or {
                    "project_type": "COBOL_MODERNIZATION",
                    "source_language": "COBOL",
                    "target_language": "JAVA"
                })
            ))

            conn.commit()
            return app_id
        finally:
            conn.close()

    def update_application(self, application: Application) -> bool:
        """Update an existing application."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE applications
                SET application_name = ?,
                    status = ?,
                    file_count = ?,
                    updated_at = ?,
                    metadata = ?
                WHERE application_id = ?
            """, (
                application.application_name,
                application.status,
                str(application.file_count or 0),
                _now_iso(),
                json.dumps(application.metadata or {}),
                application.application_id
            ))

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_application(self, application_id: str) -> bool:
        """Delete an application and its files."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Delete files first
            cursor.execute(
                "DELETE FROM files WHERE application_id = ?",
                (application_id,)
            )

            # Delete application
            cursor.execute(
                "DELETE FROM applications WHERE application_id = ?",
                (application_id,)
            )

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # =========================================================================
    # FILES - READ
    # =========================================================================

    def list_files(
        self,
        application_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[FileRecord]:
        """List files, optionally filtered by application."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if application_id:
                query = "SELECT * FROM files WHERE application_id = ? ORDER BY updated_at DESC"
                params = [application_id]
            else:
                query = "SELECT * FROM files WHERE account_id = ? ORDER BY updated_at DESC"
                params = [self.account_id]

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_file(dict(row)) for row in rows]
        finally:
            conn.close()

    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """Get a single file by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
            return self._row_to_file(dict(row)) if row else None
        finally:
            conn.close()

    def find_files_by_name(
        self,
        file_name: str,
        application_id: Optional[str] = None
    ) -> List[FileRecord]:
        """Find files by name (contains match)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if application_id:
                cursor.execute(
                    "SELECT * FROM files WHERE file_name LIKE ? AND application_id = ?",
                    (f"%{file_name}%", application_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM files WHERE file_name LIKE ? AND account_id = ?",
                    (f"%{file_name}%", self.account_id)
                )

            rows = cursor.fetchall()
            return [self._row_to_file(dict(row)) for row in rows]
        finally:
            conn.close()

    def _row_to_file(self, row: Dict[str, Any]) -> FileRecord:
        """Convert SQLite row to FileRecord model."""
        return FileRecord(
            file_id=row['file_id'],
            application_id=row['application_id'],
            file_name=row['file_name'],
            account_id=row['account_id'],
            file_type=row.get('file_type'),
            file_size=int(row.get('file_size', 0) or 0),
            status=row.get('status', 'uploaded'),
            s3_key=row.get('s3_path'),
            local_path=row.get('local_path'),
            created_at=row.get('uploaded_at'),
            updated_at=row.get('updated_at'),
            metadata={
                "cobol_job_id": row.get('cobol_job_id', ''),
                "refactor_job_id": row.get('refactor_job_id', ''),
                "dependency_job_id": row.get('dependency_job_id', ''),
                "monolith_job_id": row.get('monolith_job_id', ''),
                "data_job_id": row.get('data_job_id', ''),
                "discovery_job_id": row.get('discovery_job_id', ''),
                "architecture_job_id": row.get('architecture_job_id', ''),
                "jgv3_generation_job_id": row.get('jgv3_generation_job_id', ''),
            }
        )

    # =========================================================================
    # FILES - WRITE
    # =========================================================================

    def create_file(self, file_record: FileRecord) -> str:
        """Create a new file record."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Generate ID if not provided
            file_id = file_record.file_id or _generate_file_id(file_record.application_id)
            now = _now_iso()

            cursor.execute("""
                INSERT INTO files
                (file_id, application_id, account_id, file_name, file_type,
                 file_size, status, analysis_status, s3_path, local_path,
                 uploaded_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                file_record.application_id,
                self.account_id,
                file_record.file_name,
                file_record.file_type or 'cobol',
                str(file_record.file_size or 0),
                file_record.status or 'uploaded',
                file_record.status or 'uploaded',
                file_record.s3_key or '',
                file_record.local_path or '',
                now,
                now
            ))

            # Update application file count
            cursor.execute("""
                UPDATE applications
                SET file_count = (SELECT COUNT(*) FROM files WHERE application_id = ?),
                    updated_at = ?
                WHERE application_id = ?
            """, (file_record.application_id, now, file_record.application_id))

            conn.commit()
            return file_id
        finally:
            conn.close()

    def update_file(self, file_record: FileRecord) -> bool:
        """Update an existing file record."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE files
                SET file_name = ?,
                    file_type = ?,
                    file_size = ?,
                    status = ?,
                    analysis_status = ?,
                    s3_path = ?,
                    local_path = ?,
                    updated_at = ?
                WHERE file_id = ?
            """, (
                file_record.file_name,
                file_record.file_type,
                str(file_record.file_size or 0),
                file_record.status,
                file_record.status,
                file_record.s3_key or '',
                file_record.local_path or '',
                _now_iso(),
                file_record.file_id
            ))

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_file(self, file_id: str) -> bool:
        """Delete a file record."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get application_id first
            cursor.execute("SELECT application_id FROM files WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
            app_id = row[0] if row else None

            # Delete file
            cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
            deleted = cursor.rowcount > 0

            # Update application file count
            if app_id:
                cursor.execute("""
                    UPDATE applications
                    SET file_count = (SELECT COUNT(*) FROM files WHERE application_id = ?),
                        updated_at = ?
                    WHERE application_id = ?
                """, (app_id, _now_iso(), app_id))

            conn.commit()
            return deleted
        finally:
            conn.close()

    # =========================================================================
    # AGGREGATIONS
    # =========================================================================

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get aggregated portfolio statistics."""
        apps = self.list_applications()

        total_apps = len(apps)
        total_files = sum(app.file_count or 0 for app in apps)
        total_progress = sum(app.progress or 0 for app in apps)
        near_completion = sum(1 for app in apps if (app.progress or 0) >= 75)

        by_status: Dict[str, int] = {}
        for app in apps:
            status = app.status or "active"
            by_status[status] = by_status.get(status, 0) + 1

        avg_progress = round(total_progress / total_apps) if total_apps > 0 else 0

        return PortfolioSummary(
            total_applications=total_apps,
            total_files=total_files,
            avg_progress=avg_progress,
            near_completion=near_completion,
            by_status=by_status
        )

    def get_application_with_files(
        self,
        application_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get application with all its files."""
        app = self.get_application(application_id)
        if not app:
            return None

        files = self.list_files(application_id=application_id)

        return {
            "application": app.to_dict(),
            "files": [f.to_dict() for f in files]
        }


# =============================================================================
# MIGRATION UTILITIES
# =============================================================================

def export_to_json(provider: LocalProvider) -> Dict[str, Any]:
    """
    Export all data from local provider to JSON format.
    Useful for migration to DynamoDB.
    """
    apps = provider.list_applications()
    all_files = provider.list_files()

    return {
        "account_id": provider.account_id,
        "exported_at": _now_iso(),
        "applications": [app.to_dict() for app in apps],
        "files": [f.to_dict() for f in all_files]
    }


def import_from_json(provider: LocalProvider, data: Dict[str, Any]) -> Dict[str, int]:
    """
    Import data from JSON into local provider.
    Useful for migration from DynamoDB.
    """
    apps_imported = 0
    files_imported = 0

    for app_data in data.get("applications", []):
        app = Application.from_dict(app_data)
        provider.create_application(app)
        apps_imported += 1

    for file_data in data.get("files", []):
        file_rec = FileRecord.from_dict(file_data)
        provider.create_file(file_rec)
        files_imported += 1

    return {
        "applications_imported": apps_imported,
        "files_imported": files_imported
    }
