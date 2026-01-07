"""
Pydantic models for Dependency Mapper API.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class DependencyMapperRequest(BaseModel):
    """Request model for Dependency Mapper Analysis."""
    scout_account_id: str
    application_name: str
    source_type: str = "cobol"  # "cobol" or "java"


class DependencyMapperResponse(BaseModel):
    """Response model for Dependency Mapper."""
    success: bool
    job_id: str
    source_type: str
    status: str
    source_path: str
    artifacts_path: str
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = {}
    artifacts: Dict[str, str] = {}


class DependencyMapperStatusResponse(BaseModel):
    """Response model for dependency mapper job status."""
    job_id: str
    flow_type: str
    status: str
    artifacts_path: str
    created_at: str
    updated_at: str


class DependencyMapperResultsResponse(BaseModel):
    """Response model for dependency mapper results overview."""
    job_id: str
    status: str
    source_type: str
    artifacts_path: str
    json_artifacts: List[str] = []
    summary: Dict[str, Any] = {}


class ComparisonRequest(BaseModel):
    """Request model for COBOL vs Java comparison."""
    scout_account_id: str
    application_name: str


class ComparisonResponse(BaseModel):
    """Response model for comparison analysis."""
    success: bool
    job_id: str
    status: str
    cobol_summary: Dict[str, Any] = {}
    java_summary: Dict[str, Any] = {}
    gaps: List[Dict[str, Any]] = []
    insights: List[str] = []
    recommendations: List[Dict[str, Any]] = []
    artifacts_path: str = ""
    error: Optional[str] = None
