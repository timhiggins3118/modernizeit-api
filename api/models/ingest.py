"""
Ingest Models

Pydantic models for Ingest API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """
    Request model for local ingest operation.

    This model captures the workflow context for local execution.
    """
    scout_account_id: str = Field(..., description="Scout account identifier")
    application_name: str = Field(..., description="Application name")
    zip_file_path: str = Field(..., description="Path to ZIP file to ingest")
    working_folder: str = Field(..., description="Working folder for output")
    generate_type_mappings: bool = Field(default=True, description="Generate type mapping files")
    source_lang: str = Field(default="cobol", description="Source language (cobol, cpp, etc.)")
    target_lang: str = Field(default="java", description="Target language (java, dotnet, etc.)")
    source_hash: Optional[str] = Field(None, description="Optional pre-computed source hash")
    job_id: Optional[str] = Field(None, description="Optional job ID to use")

    class Config:
        json_schema_extra = {
            "example": {
                "scout_account_id": "acct123",
                "application_name": "mycobolapp",
                "zip_file_path": "/path/to/source.zip",
                "working_folder": "/path/to/output",
                "generate_type_mappings": True,
                "source_lang": "cobol",
                "target_lang": "java"
            }
        }


class IngestResponse(BaseModel):
    """
    Response model for ingest operation.

    Matches the AWS API Gateway response contract.
    """
    job_id: str = Field(..., description="Unique job identifier")
    source_hash: str = Field(..., description="SHA-256 hash of source content")
    duplicate: bool = Field(default=False, description="True if content already existed")
    file_count: Optional[int] = Field(None, description="Number of files extracted")
    files_processed: Optional[int] = Field(None, description="Number of files processed")
    paths: Dict[str, str] = Field(default_factory=dict, description="S3/local paths created")
    summary: Optional[Dict[str, int]] = Field(None, description="Classification summary")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "ingest_job_acct123_myapp_1733846400_abc12345",
                "source_hash": "abc123def456...",
                "duplicate": False,
                "file_count": 25,
                "files_processed": 25,
                "paths": {
                    "upload_root": "s3://code-transformation-v2/acct123/myapp/shared/uploads/abc123/",
                    "extracted": "s3://code-transformation-v2/acct123/myapp/shared/uploads/abc123/extracted/",
                    "catalogs": "s3://code-transformation-v2/acct123/myapp/shared/catalogs/abc123/"
                },
                "summary": {
                    "cobol": 15,
                    "copybook": 5,
                    "jcl": 3,
                    "sql": 2,
                    "config": 0,
                    "documentation": 0,
                    "unknown": 0
                }
            }
        }


class IngestStatusResponse(BaseModel):
    """
    Status response for checking ingest job status.

    Matches AWS API pattern: POST /start -> GET /status -> GET /results
    """
    job_id: str = Field(..., description="Job identifier")
    state: str = Field(..., description="Job state (pending, running, completed, failed)")
    progress: float = Field(default=0.0, description="Progress percentage (0.0 to 1.0)")
    message: Optional[str] = Field(None, description="Status message")
    started_at: Optional[datetime] = Field(None, description="When job started")
    finished_at: Optional[datetime] = Field(None, description="When job finished")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "ingest_job_acct123_myapp_1733846400_abc12345",
                "state": "completed",
                "progress": 1.0,
                "message": "Ingest completed successfully",
                "started_at": "2024-12-10T12:00:00Z",
                "finished_at": "2024-12-10T12:00:05Z"
            }
        }
