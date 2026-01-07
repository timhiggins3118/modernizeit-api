"""
Pydantic models for Code Analysis API.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class CodeAnalysisRequest(BaseModel):
    """Request model for Code Analysis."""
    scout_account_id: str
    application_name: str
    source_hash: Optional[str] = None  # Optional, uses latest from ingest if omitted
    main_program: Optional[str] = None  # Optional, auto-detect if omitted
    generate_java: bool = True
    generate_graphs: bool = True


class CodeAnalysisResponse(BaseModel):
    """Response model for Code Analysis."""
    success: bool
    job_id: str
    status: str
    artifacts_path: str
    main_program: Optional[str] = None
    base_name: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = {}
    artifacts: Dict[str, Any] = {}


class CodeAnalysisStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    flow_type: str
    status: str
    artifacts_path: str
    created_at: str
    updated_at: str
