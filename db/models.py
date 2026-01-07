"""
Shared Data Models for the Data Provider Layer.

These models are backend-agnostic - used by SQLite, DynamoDB, MongoDB, etc.
All providers work with these same models.

Created: December 31, 2025
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ApplicationStatus(str, Enum):
    """Application workflow status."""
    STARTING = "Starting"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FAILED = "Failed"


class FileStatus(str, Enum):
    """File processing status."""
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "Analyzed"
    FAILED = "failed"


class WorkflowStep(str, Enum):
    """The 4-step modernization workflow."""
    ANALYSIS = "analysis"
    OT = "ot"  # Optimization & Transformation
    QA = "qa"
    ARCHITECTURE = "architecture"


# =============================================================================
# APPLICATION MODEL
# =============================================================================

@dataclass
class Application:
    """
    Application record - a project being modernized.

    Maps to:
      - DynamoDB: {account_id}_applications table
      - SQLite: applications table
    """
    application_id: str
    application_name: str
    account_id: str = ""
    description: Optional[str] = None
    status: str = ApplicationStatus.STARTING.value
    progress: int = 0
    file_count: int = 0
    current_step: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Application":
        """Create from dictionary."""
        return cls(
            application_id=data.get('application_id', data.get('id', '')),
            application_name=data.get('application_name', data.get('name', '')),
            account_id=data.get('account_id', ''),
            description=data.get('description'),
            status=data.get('status', ApplicationStatus.STARTING.value),
            progress=data.get('progress', 0),
            file_count=data.get('file_count', data.get('fileCount', 0)),
            current_step=data.get('current_step', data.get('currentStep')),
            created_at=data.get('created_at', data.get('createdAt')),
            updated_at=data.get('updated_at', data.get('updatedAt')),
            metadata=data.get('metadata', {})
        )


# =============================================================================
# FILE MODEL
# =============================================================================

@dataclass
class FileRecord:
    """
    File record - a COBOL file within an application.

    Maps to:
      - DynamoDB: {account_id}_files table
      - SQLite: files table
    """
    file_id: str
    application_id: str
    file_name: str
    account_id: str = ""
    file_type: Optional[str] = None  # COBOL_PROGRAM, COPYBOOK, JCL, etc.
    file_size: Optional[int] = None
    status: str = FileStatus.UPLOADED.value
    s3_key: Optional[str] = None
    local_path: Optional[str] = None
    total_lines: Optional[int] = None
    paragraphs: Optional[int] = None
    complexity: Optional[str] = None  # LOW, MEDIUM, HIGH
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileRecord":
        """Create from dictionary."""
        return cls(
            file_id=data.get('file_id', data.get('id', '')),
            application_id=data.get('application_id', ''),
            file_name=data.get('file_name', data.get('fileName', '')),
            account_id=data.get('account_id', ''),
            file_type=data.get('file_type', data.get('fileType')),
            file_size=data.get('file_size', data.get('fileSize')),
            status=data.get('status', FileStatus.UPLOADED.value),
            s3_key=data.get('s3_key', data.get('s3Key')),
            local_path=data.get('local_path', data.get('localPath')),
            total_lines=data.get('total_lines', data.get('totalLines')),
            paragraphs=data.get('paragraphs'),
            complexity=data.get('complexity'),
            created_at=data.get('created_at', data.get('createdAt')),
            updated_at=data.get('updated_at', data.get('updatedAt')),
            analysis_results=data.get('analysis_results', data.get('analysisResults', {})),
            metadata=data.get('metadata', {})
        )


# =============================================================================
# WORKFLOW STATE MODEL
# =============================================================================

@dataclass
class WorkflowState:
    """
    Workflow state - tracks progress through the 4-step workflow.

    Maps to:
      - DynamoDB: {account_id}_workflow_state or embedded in application
      - SQLite: workflow_state table
    """
    application_id: str
    current_step: str = WorkflowStep.ANALYSIS.value
    analysis_complete: bool = False
    ot_complete: bool = False
    qa_complete: bool = False
    architecture_complete: bool = False
    last_job_id: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def calculate_progress(self) -> int:
        """Calculate progress percentage based on completed steps."""
        completed = sum([
            self.analysis_complete,
            self.ot_complete,
            self.qa_complete,
            self.architecture_complete
        ])
        return int((completed / 4) * 100)


# =============================================================================
# PORTFOLIO SUMMARY MODEL
# =============================================================================

@dataclass
class PortfolioSummary:
    """
    Aggregated portfolio stats - for the dashboard view.
    """
    total_applications: int = 0
    total_files: int = 0
    avg_progress: int = 0
    near_completion: int = 0  # Apps with 75%+ progress
    by_status: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
