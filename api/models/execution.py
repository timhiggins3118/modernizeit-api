"""
Execution Models

Pydantic models for execution configuration and results.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionConfig(BaseModel):
    """
    Configuration for Lambda execution.

    Used by LocalLambdaExecutor and engine runners.
    """
    project_path: str = Field(..., description="Path to Lambda project")
    handler: str = Field(default="handler.lambda_handler", description="Handler reference (module.function)")
    runtime: str = Field(default="python3.11", description="Python runtime")
    timeout_seconds: int = Field(default=300, description="Execution timeout in seconds")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_folder: Optional[str] = Field(None, description="Base folder for local storage (S3 redirection)")


class EngineResult(BaseModel):
    """
    Standard result from any engine execution.

    All engines return this common structure.
    """
    success: bool = Field(..., description="Whether execution succeeded")
    job_id: Optional[str] = Field(None, description="Job ID if created")
    payload: Optional[Dict[str, Any]] = Field(None, description="Response payload from Lambda")
    logs: List[str] = Field(default_factory=list, description="Execution logs")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "job_id": "ingest_job_acct123_myapp_1733846400_abc12345",
                "payload": {
                    "statusCode": 201,
                    "body": "{\"job_id\": \"...\", \"source_hash\": \"...\"}"
                },
                "logs": ["[12:00:00.123] Starting execution..."],
                "error": None,
                "duration_ms": 1500
            }
        }
