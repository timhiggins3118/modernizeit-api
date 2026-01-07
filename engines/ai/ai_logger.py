"""
AI Request/Response Logger

Logs all AI interactions for monitoring, debugging, and auditing.

Features:
- SQLite database storage for querying
- JSON file backup for export
- Configurable retention
- Request/response capture with metadata
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings


class AILogger:
    """
    Logs AI requests and responses to SQLite database.

    Thread-safe singleton pattern for global access.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.enabled = getattr(settings, 'ai_logging_enabled', True)
        self.db_path = Path(settings.base_local_path) / "ai_logs.db"
        self.json_log_dir = Path(settings.base_local_path) / "ai_logs"
        self.retention_days = getattr(settings, 'ai_log_retention_days', 30)

        # Create directories
        self.json_log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                model TEXT NOT NULL,
                purpose TEXT,
                prompt_preview TEXT,
                prompt_length INTEGER,
                response_preview TEXT,
                response_length INTEGER,
                duration_ms INTEGER,
                success INTEGER,
                error TEXT,
                tokens_input INTEGER,
                tokens_output INTEGER,
                temperature REAL,
                max_tokens INTEGER,
                metadata TEXT
            )
        """)

        # Index for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_model ON ai_logs(model)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_success ON ai_logs(success)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purpose ON ai_logs(purpose)")

        conn.commit()
        conn.close()

    def log(
        self,
        model: str,
        prompt: str,
        response: Optional[str],
        duration_ms: int,
        success: bool,
        error: Optional[str] = None,
        purpose: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an AI request/response.

        Args:
            model: Model ID used
            prompt: The full prompt sent
            response: The full response received (None if failed)
            duration_ms: Request duration in milliseconds
            success: Whether the request succeeded
            error: Error message if failed
            purpose: Purpose/category of the request
            temperature: Temperature setting used
            max_tokens: Max tokens setting used
            tokens_input: Input token count (if available)
            tokens_output: Output token count (if available)
            metadata: Additional metadata dict

        Returns:
            Log entry ID
        """
        if not self.enabled:
            return ""

        log_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()

        # Create previews (first 500 chars)
        prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
        response_preview = ""
        if response:
            response_preview = response[:500] + "..." if len(response) > 500 else response

        # Store in database
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO ai_logs (
                    id, timestamp, model, purpose, prompt_preview, prompt_length,
                    response_preview, response_length, duration_ms, success, error,
                    tokens_input, tokens_output, temperature, max_tokens, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                timestamp,
                model,
                purpose,
                prompt_preview,
                len(prompt),
                response_preview,
                len(response) if response else 0,
                duration_ms,
                1 if success else 0,
                error,
                tokens_input,
                tokens_output,
                temperature,
                max_tokens,
                json.dumps(metadata) if metadata else None
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[AILogger] Database write failed: {e}")

        # Also write full content to JSON file for detailed review
        try:
            log_file = self.json_log_dir / f"{timestamp[:10]}.jsonl"
            log_entry = {
                "id": log_id,
                "timestamp": timestamp,
                "model": model,
                "purpose": purpose,
                "prompt": prompt,
                "response": response,
                "duration_ms": duration_ms,
                "success": success,
                "error": error,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "metadata": metadata
            }

            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"[AILogger] JSON write failed: {e}")

        return log_id

    def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        model: Optional[str] = None,
        purpose: Optional[str] = None,
        success_only: Optional[bool] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Query logs with filters.

        Args:
            limit: Maximum entries to return
            offset: Offset for pagination
            model: Filter by model
            purpose: Filter by purpose
            success_only: Filter by success status
            since: Filter by start time
            until: Filter by end time

        Returns:
            List of log entries
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM ai_logs WHERE 1=1"
        params = []

        if model:
            query += " AND model = ?"
            params.append(model)

        if purpose:
            query += " AND purpose = ?"
            params.append(purpose)

        if success_only is not None:
            query += " AND success = ?"
            params.append(1 if success_only else 0)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_stats(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics.

        Args:
            since: Start time for stats
            until: End time for stats

        Returns:
            Statistics dict
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        where_clause = "WHERE 1=1"
        params = []

        if since:
            where_clause += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            where_clause += " AND timestamp <= ?"
            params.append(until.isoformat())

        # Total counts
        cursor.execute(f"SELECT COUNT(*) FROM ai_logs {where_clause}", params)
        total_requests = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(*) FROM ai_logs {where_clause} AND success = 1", params)
        successful_requests = cursor.fetchone()[0]

        # Average duration
        cursor.execute(f"SELECT AVG(duration_ms) FROM ai_logs {where_clause}", params)
        avg_duration = cursor.fetchone()[0] or 0

        # Total tokens
        cursor.execute(f"""
            SELECT
                COALESCE(SUM(tokens_input), 0),
                COALESCE(SUM(tokens_output), 0)
            FROM ai_logs {where_clause}
        """, params)
        tokens = cursor.fetchone()
        total_input_tokens = tokens[0]
        total_output_tokens = tokens[1]

        # By model
        cursor.execute(f"""
            SELECT model, COUNT(*) as count, AVG(duration_ms) as avg_duration
            FROM ai_logs {where_clause}
            GROUP BY model
            ORDER BY count DESC
        """, params)
        by_model = [{"model": r[0], "count": r[1], "avg_duration_ms": r[2]} for r in cursor.fetchall()]

        # By purpose
        cursor.execute(f"""
            SELECT purpose, COUNT(*) as count
            FROM ai_logs {where_clause}
            GROUP BY purpose
            ORDER BY count DESC
        """, params)
        by_purpose = [{"purpose": r[0] or "unknown", "count": r[1]} for r in cursor.fetchall()]

        # Errors
        cursor.execute(f"""
            SELECT error, COUNT(*) as count
            FROM ai_logs {where_clause} AND success = 0 AND error IS NOT NULL
            GROUP BY error
            ORDER BY count DESC
            LIMIT 10
        """, params)
        top_errors = [{"error": r[0], "count": r[1]} for r in cursor.fetchall()]

        conn.close()

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": total_requests - successful_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "by_model": by_model,
            "by_purpose": by_purpose,
            "top_errors": top_errors
        }

    def get_log_detail(self, log_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for a specific log entry.

        Reads from JSON file to get full prompt/response.
        """
        # First get metadata from DB
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM ai_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        result = dict(row)

        # Try to get full content from JSON file
        timestamp = result['timestamp']
        date_str = timestamp[:10]
        log_file = self.json_log_dir / f"{date_str}.jsonl"

        if log_file.exists():
            with open(log_file, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get('id') == log_id:
                        result['full_prompt'] = entry.get('prompt')
                        result['full_response'] = entry.get('response')
                        break

        return result

    def cleanup_old_logs(self, days: Optional[int] = None):
        """Remove logs older than retention period."""
        retention = days or self.retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention)

        # Clean database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ai_logs WHERE timestamp < ?", (cutoff.isoformat(),))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        # Clean JSON files
        for log_file in self.json_log_dir.glob("*.jsonl"):
            try:
                file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    log_file.unlink()
            except ValueError:
                pass

        return deleted


# Global singleton instance
_logger = None


def get_logger() -> AILogger:
    """Get the global AILogger instance."""
    global _logger
    if _logger is None:
        _logger = AILogger()
    return _logger


def log_request(
    model: str,
    prompt: str,
    response: Optional[str],
    duration_ms: int,
    success: bool,
    **kwargs
) -> str:
    """Convenience function to log a request."""
    return get_logger().log(model, prompt, response, duration_ms, success, **kwargs)
