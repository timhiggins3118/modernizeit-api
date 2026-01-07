"""
Pydantic models for Test Generation API.

Test Generation is the testing step in the ModernizeIT pipeline.
It takes Java code from Code Analysis/Refactor and generates JUnit tests.

Two modes:
1. Test Stubs - Quick scaffolding with TODOs (no AI)
2. Smart Tests - AI-powered meaningful tests with real assertions
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class TestFramework(str, Enum):
    """Test framework to use."""
    JUNIT5 = "junit5"
    TESTNG = "testng"


class MockFramework(str, Enum):
    """Mock framework to use."""
    MOCKITO = "mockito"
    MOCKK = "mockk"


class TestSource(str, Enum):
    """Source of Java code to generate tests for."""
    ANALYSIS = "analysis"  # Use Java from Code Analysis (raw translation)
    REFACTOR = "refactor"  # Use Java from Code Refactor (modernized)


class CoverageTarget(str, Enum):
    """Target code coverage level."""
    BASIC = "60"
    STANDARD = "80"
    FULL = "100"


# =============================================================================
# Test Stubs (No AI) - Quick scaffolding
# =============================================================================

class TestStubsOptions(BaseModel):
    """Configuration options for Test Stubs generation (no AI)."""
    framework: TestFramework = Field(
        default=TestFramework.JUNIT5,
        description="Test framework to use"
    )
    include_mocks: bool = Field(
        default=True,
        description="Include Mockito mock setup"
    )
    fail_on_todo: bool = Field(
        default=True,
        description="Tests fail with TODO until implemented"
    )


class TestStubsRequest(BaseModel):
    """Request model for starting a Test Stubs job."""
    scout_account_id: str = Field(
        ...,
        description="Account identifier"
    )
    application_name: str = Field(
        ...,
        description="Application name"
    )
    source: TestSource = Field(
        default=TestSource.REFACTOR,
        description="Source of Java code: 'analysis' or 'refactor'"
    )
    options: TestStubsOptions = Field(
        default_factory=TestStubsOptions,
        description="Test stub generation options"
    )


class TestStubsResponse(BaseModel):
    """Response model for starting a Test Stubs job."""
    success: bool
    job_id: str
    status: str
    message: str
    created_at: str
    error: Optional[str] = None


# =============================================================================
# Smart Tests (AI-Powered) - Meaningful validation
# =============================================================================

class SmartTestsOptions(BaseModel):
    """Configuration options for Smart Tests generation (AI-powered)."""
    framework: TestFramework = Field(
        default=TestFramework.JUNIT5,
        description="Test framework to use"
    )
    mock_framework: MockFramework = Field(
        default=MockFramework.MOCKITO,
        description="Mock framework to use"
    )
    unit_tests: bool = Field(
        default=True,
        description="Generate unit tests for methods"
    )
    validation_tests: bool = Field(
        default=True,
        description="Generate validation tests from copybook constraints"
    )
    integration_tests: bool = Field(
        default=False,
        description="Generate controller integration tests"
    )
    coverage_target: CoverageTarget = Field(
        default=CoverageTarget.STANDARD,
        description="Target code coverage: 60, 80, or 100%"
    )
    max_ai_calls: int = Field(
        default=50,
        description="Maximum AI calls for cost control",
        ge=1,
        le=200
    )


class SmartTestsRequest(BaseModel):
    """Request model for starting a Smart Tests job."""
    scout_account_id: str = Field(
        ...,
        description="Account identifier"
    )
    application_name: str = Field(
        ...,
        description="Application name"
    )
    source: TestSource = Field(
        default=TestSource.REFACTOR,
        description="Source of Java code: 'analysis' or 'refactor'"
    )
    options: SmartTestsOptions = Field(
        default_factory=SmartTestsOptions,
        description="Smart test generation options"
    )


class SmartTestsResponse(BaseModel):
    """Response model for starting a Smart Tests job."""
    success: bool
    job_id: str
    status: str
    message: str
    created_at: str
    ai_calls_used: int = 0
    error: Optional[str] = None


# =============================================================================
# Shared Response Models
# =============================================================================

class TestGenerationStatusResponse(BaseModel):
    """Response model for job status (both stubs and smart)."""
    success: bool
    job_id: str
    status: str  # running, completed, failed
    progress: int = 0
    phase: str = ""
    phases_completed: List[str] = []
    test_type: str = ""  # stubs or smart
    tests_generated: int = 0
    classes_covered: int = 0
    methods_covered: int = 0
    ai_calls_used: int = 0
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class GeneratedTest(BaseModel):
    """A single generated test file."""
    file_path: str
    class_name: str
    test_count: int
    methods_tested: List[str] = []


class TestGenerationResultsResponse(BaseModel):
    """Response model for test generation results."""
    success: bool
    job_id: str
    test_type: str  # stubs or smart
    framework: str
    tests_generated: int
    classes_covered: int
    methods_covered: int
    output_path: str
    tests: List[GeneratedTest] = []
    ai_calls_used: int = 0
    duration_ms: int = 0


class TestStatistics(BaseModel):
    """Statistics about generated tests."""
    total_tests: int = 0
    unit_tests: int = 0
    validation_tests: int = 0
    integration_tests: int = 0
    classes_covered: int = 0
    methods_covered: int = 0
    ai_calls_used: int = 0


class JobSummary(BaseModel):
    """Summary of a test generation job for listing."""
    job_id: str
    status: str
    test_type: str  # stubs or smart
    source: str
    created_at: str
    tests_generated: int


class TestGenerationJobsResponse(BaseModel):
    """Response model for listing test generation jobs."""
    success: bool
    scout_account_id: str
    application_name: str
    jobs: List[JobSummary] = []
