"""
Pydantic models for Java Packaging API.

Java Packaging is the final step in the ModernizeIT pipeline.
It takes existing Java code from Code Analysis or Code Refactor
and packages it into a production-ready Spring Boot application.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class JavaSource(str, Enum):
    """Source of Java code to package."""
    ANALYSIS = "analysis"  # Use Java from Code Analysis (raw translation)
    REFACTOR = "refactor"  # Use Java from Code Refactor (modernized)


class JavaPackagingOptions(BaseModel):
    """Configuration options for Java packaging."""
    run_validation: bool = Field(
        default=True,
        description="Run AST validation on Java files"
    )
    full_compile: bool = Field(
        default=False,
        description="Run full javac compilation (slower, more thorough)"
    )
    include_docker: bool = Field(
        default=True,
        description="Include Dockerfile and docker-compose.yml"
    )
    include_tests: bool = Field(
        default=True,
        description="Generate JUnit 5 test scaffolding"
    )
    spring_boot_version: str = Field(
        default="3.2.0",
        description="Spring Boot version for pom.xml"
    )
    java_version: str = Field(
        default="17",
        description="Java version for compilation target"
    )


class JavaPackagingRequest(BaseModel):
    """Request model for starting a Java packaging job."""
    scout_account_id: str = Field(
        ...,
        description="Account identifier"
    )
    application_name: str = Field(
        ...,
        description="Application name"
    )
    source: JavaSource = Field(
        default=JavaSource.REFACTOR,
        description="Source of Java code: 'analysis' or 'refactor'"
    )
    options: JavaPackagingOptions = Field(
        default_factory=JavaPackagingOptions,
        description="Packaging options"
    )


class JavaPackagingResponse(BaseModel):
    """Response model for starting a Java packaging job."""
    success: bool
    job_id: str
    status: str
    message: str
    created_at: str
    error: Optional[str] = None


class ValidationSummary(BaseModel):
    """Summary of Java validation results."""
    status: str  # PASSED, PASSED_WITH_WARNINGS, FAILED
    total_files: int = 0
    valid_files: int = 0
    invalid_files: int = 0
    warnings: int = 0
    todos: int = 0


class PackageStatistics(BaseModel):
    """Statistics about the generated package."""
    services_packaged: int = 0
    entities_packaged: int = 0
    controllers_generated: int = 0
    repositories_generated: int = 0
    tests_generated: int = 0
    total_files: int = 0
    package_size_bytes: int = 0


class JavaPackagingStatusResponse(BaseModel):
    """Response model for job status."""
    success: bool
    job_id: str
    status: str  # running, completed, failed
    progress: int = 0
    phase: str = ""
    phases_completed: List[str] = []
    statistics: Optional[PackageStatistics] = None
    validation: Optional[ValidationSummary] = None
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ValidationIssue(BaseModel):
    """A single validation issue."""
    file: str
    type: str  # error, warning
    message: str
    line: Optional[int] = None


class JavaPackagingValidationResponse(BaseModel):
    """Response model for validation report."""
    success: bool
    job_id: str
    validation_method: str  # ast, compile
    overall_status: str
    summary: ValidationSummary
    issues: List[ValidationIssue] = []


class JobSummary(BaseModel):
    """Summary of a packaging job for listing."""
    job_id: str
    status: str
    source: str
    created_at: str
    package_ready: bool


class JavaPackagingJobsResponse(BaseModel):
    """Response model for listing jobs."""
    success: bool
    scout_account_id: str
    application_name: str
    jobs: List[JobSummary] = []
