"""
Pydantic models for Code Refactor API.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class CodeRefactorRequest(BaseModel):
    """Request model for Code Refactor Analysis."""
    scout_account_id: str
    application_name: str
    class_name: Optional[str] = None  # Specific Java class to analyze (auto-detect if omitted)
    mode: str = "analyze"  # "analyze", "transform", or "full"
    use_ai: bool = True  # Whether to use Bedrock AI for analysis
    recipes_to_apply: Optional[List[str]] = None  # Specific recipe IDs (transform mode only)
    auto_transform: bool = True  # Automatically apply transformations after analyze


class CodeRefactorResponse(BaseModel):
    """Response model for Code Refactor."""
    success: bool
    job_id: str
    phase: str  # "analyze" or "transform"
    status: str
    java_file: str
    class_name: str
    artifacts_path: str
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = {}
    artifacts: Dict[str, str] = {}


class CodeRefactorStatusResponse(BaseModel):
    """Response model for refactor job status."""
    job_id: str
    flow_type: str
    status: str
    artifacts_path: str
    created_at: str
    updated_at: str


class CodeRefactorResultsResponse(BaseModel):
    """Response model for refactor results overview."""
    job_id: str
    status: str
    artifacts_path: str
    json_artifacts: List[str] = []
    summary: Dict[str, Any] = {}


class CodeTransformRequest(BaseModel):
    """Request model for Code Transform (Phase 2)."""
    scout_account_id: str
    application_name: str
    recipes_to_apply: Any  # List of recipe IDs or "all"


class CodeTransformResponse(BaseModel):
    """Response model for Code Transform."""
    success: bool
    job_id: str
    status: str
    original_file: str
    output_path: str
    recipes_applied: int
    changes_made: List[Dict[str, Any]] = []
    error: Optional[str] = None
    duration_ms: int = 0
