"""
Architecture Recommender API Models

Pydantic models for Architecture Recommender flow.
Evidence-based AWS architecture recommendations with cross-validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class Severity(str, Enum):
    """Severity levels for warnings."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConfidenceLevel(str, Enum):
    """Confidence level for recommendations."""
    HIGH = "HIGH"      # 0.85+
    MEDIUM = "MEDIUM"  # 0.70-0.84
    LOW = "LOW"        # <0.70


class ComputeService(str, Enum):
    """AWS compute service options."""
    LAMBDA = "AWS Lambda"
    ECS_FARGATE = "Amazon ECS/Fargate"
    EC2 = "Amazon EC2"
    BATCH = "AWS Batch"


class DatabaseService(str, Enum):
    """AWS database service options."""
    AURORA_POSTGRESQL = "Aurora PostgreSQL"
    AURORA_MYSQL = "Aurora MySQL"
    RDS_POSTGRESQL = "RDS PostgreSQL"
    RDS_MYSQL = "RDS MySQL"
    DYNAMODB = "DynamoDB"
    NONE = "None"


class StorageService(str, Enum):
    """AWS storage service options."""
    S3 = "Amazon S3"
    EFS = "Amazon EFS"
    S3_GLACIER = "S3 Glacier"


# =============================================================================
# Request Models
# =============================================================================

class ArchitectureRequest(BaseModel):
    """Request to run Architecture Recommender analysis."""
    scout_account_id: str = Field(..., description="Customer account ID")
    application_name: str = Field(..., description="Application name")
    source_path: Optional[str] = Field(
        default=None,
        description="Path to source directory (optional if using job references)"
    )
    discovery_job_id: Optional[str] = Field(
        default=None,
        description="Reference to completed Discovery job"
    )
    data_analysis_job_id: Optional[str] = Field(
        default=None,
        description="Reference to completed Data Analysis job"
    )
    code_analysis_job_id: Optional[str] = Field(
        default=None,
        description="Reference to completed Code Analysis job"
    )
    code_refactor_job_id: Optional[str] = Field(
        default=None,
        description="Reference to completed Code Refactor job"
    )
    java_source_path: Optional[str] = Field(
        default=None,
        description="Path to generated Java code (from Code Analysis)"
    )


# =============================================================================
# Java Analysis Models
# =============================================================================

class DependencyInfo(BaseModel):
    """Detected dependency from pom.xml or build.gradle."""
    group_id: str
    artifact_id: str
    version: Optional[str] = None
    category: str = Field(description="database, web, messaging, aws, testing, etc.")
    aws_implication: str = Field(description="What this implies for AWS architecture")


class AnnotationCount(BaseModel):
    """Count of detected annotations."""
    annotation: str
    count: int
    aws_implication: str


class ClassBreakdown(BaseModel):
    """Breakdown of Java classes by type."""
    controllers: int = 0
    services: int = 0
    repositories: int = 0
    entities: int = 0
    batch_jobs: int = 0
    components: int = 0
    configurations: int = 0
    total: int = 0


class EntryPoint(BaseModel):
    """Detected entry point (REST endpoint, scheduled task, listener)."""
    class_name: str
    entry_type: str = Field(description="REST, SCHEDULED, SQS_LISTENER, KAFKA_LISTENER")
    endpoint_count: Optional[int] = None
    cron_expression: Optional[str] = None
    trigger: Optional[str] = None


class JavaAnalysis(BaseModel):
    """Complete Java code analysis results."""
    build_tool: str = Field(description="maven, gradle, or unknown")
    framework: Optional[str] = Field(
        default=None,
        description="spring-boot-X.X, quarkus, micronaut, etc."
    )
    java_version: Optional[str] = None
    dependencies: Dict[str, List[DependencyInfo]] = Field(
        default_factory=dict,
        description="Dependencies by category: database, web, messaging, aws"
    )
    annotations_found: List[AnnotationCount] = Field(default_factory=list)
    class_breakdown: ClassBreakdown = Field(default_factory=ClassBreakdown)
    entry_points: List[EntryPoint] = Field(default_factory=list)
    packages_analyzed: int = 0
    files_analyzed: int = 0


# =============================================================================
# Evidence Models
# =============================================================================

class Evidence(BaseModel):
    """Evidence item supporting a recommendation."""
    source: str = Field(description="java, discovery, data_analysis, code_analysis, code_refactor")
    finding: str = Field(description="What was found that supports this recommendation")


class ValidationWarning(BaseModel):
    """Warning from cross-validation between sources."""
    warning_type: str = Field(description="SOURCE_CONFLICT, MISSING_DATA, ASSUMPTION")
    severity: Severity
    description: str
    sources: Dict[str, str] = Field(
        default_factory=dict,
        description="What each source says"
    )
    possible_causes: List[str] = Field(default_factory=list)
    recommendation: str


# =============================================================================
# Recommendation Models
# =============================================================================

class TradeOffs(BaseModel):
    """Pros and cons of an alternative."""
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)


class AlternativeRecommendation(BaseModel):
    """Alternative recommendation with trade-offs."""
    service: str
    reason: str = Field(description="When to consider this alternative")
    trade_offs: TradeOffs


class LambdaFunction(BaseModel):
    """Lambda function recommendation."""
    name: str
    source_class: str = Field(description="Java class this maps to")
    memory_mb: int = Field(default=1024)
    timeout_seconds: int = Field(default=30)
    trigger: str = Field(description="API Gateway, CloudWatch Events, SQS, etc.")


class ComputeRecommendation(BaseModel):
    """Compute service recommendation with evidence."""
    primary: Dict[str, Any] = Field(default_factory=dict)
    alternative: Optional[AlternativeRecommendation] = None

    # Primary fields at top level for convenience
    service: ComputeService = Field(description="Primary compute service")
    runtime: str = Field(default="java17")
    functions: List[LambdaFunction] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: List[Evidence] = Field(default_factory=list)


class DatabaseRecommendation(BaseModel):
    """Database service recommendation with evidence."""
    service: DatabaseService = Field(description="Primary database service or None")
    instance_class: Optional[str] = Field(default=None, description="db.t4g.medium, etc.")
    storage_gb: Optional[int] = None
    multi_az: bool = False
    confidence: float = Field(ge=0, le=1)
    evidence: List[Evidence] = Field(default_factory=list)
    alternative: Optional[AlternativeRecommendation] = None
    alternative_storage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="If no DB needed, alternative storage like S3"
    )


class APIRecommendation(BaseModel):
    """API Gateway recommendation with evidence."""
    required: bool = Field(description="Whether API Gateway is needed")
    api_type: Optional[str] = Field(
        default=None,
        description="REST, HTTP, or WebSocket"
    )
    auth_type: Optional[str] = Field(
        default=None,
        description="COGNITO, IAM, API_KEY, or NONE"
    )
    endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: List[Evidence] = Field(default_factory=list)
    alternative: Optional[AlternativeRecommendation] = None


class S3Bucket(BaseModel):
    """S3 bucket configuration."""
    name_suffix: str = Field(description="Suffix for bucket name")
    purpose: str
    storage_class: str = Field(default="STANDARD")
    lifecycle_days: Optional[int] = None


class StorageRecommendation(BaseModel):
    """Storage recommendation with evidence."""
    buckets: List[S3Bucket] = Field(default_factory=list)
    efs_required: bool = False
    confidence: float = Field(ge=0, le=1)
    evidence: List[Evidence] = Field(default_factory=list)


class SecurityRecommendation(BaseModel):
    """Security configuration recommendation."""
    vpc_required: bool = True
    private_subnets: bool = True
    nat_gateway: bool = True
    encryption_at_rest: bool = True
    encryption_in_transit: bool = True
    secrets_manager: bool = True
    waf_required: bool = False
    confidence: float = Field(ge=0, le=1)
    evidence: List[Evidence] = Field(default_factory=list)


# =============================================================================
# Cost Estimation Models
# =============================================================================

class CostCalculation(BaseModel):
    """Details of how a cost was calculated."""
    service: str
    monthly_cost: float
    calculation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters used in calculation"
    )
    evidence: str = Field(description="What data this estimate is based on")


class CostEstimate(BaseModel):
    """Evidence-based cost estimates."""
    compute_cost: CostCalculation
    database_cost: Optional[CostCalculation] = None
    storage_cost: Optional[CostCalculation] = None
    api_cost: Optional[CostCalculation] = None
    other_costs: List[CostCalculation] = Field(default_factory=list)
    total_monthly: float
    total_annual: float
    vs_mainframe_savings_percent: Optional[float] = None
    confidence: float = Field(ge=0, le=1)
    notes: List[str] = Field(default_factory=list)


# =============================================================================
# Traceability Models
# =============================================================================

class ServiceMapping(BaseModel):
    """Mapping from Java class to AWS service."""
    java_class: str
    java_package: str
    aws_service: str
    aws_resource_name: str
    entry_type: str


class Traceability(BaseModel):
    """Complete traceability from Java to AWS."""
    mappings: List[ServiceMapping] = Field(default_factory=list)
    unmapped_classes: List[str] = Field(
        default_factory=list,
        description="Classes that couldn't be mapped"
    )


# =============================================================================
# IaC Template Models
# =============================================================================

class IaCTemplate(BaseModel):
    """Generated IaC template information."""
    template_name: str
    template_type: str = Field(description="cdk, cloudformation, terraform")
    file_path: str
    resources: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class IaCOutput(BaseModel):
    """All generated IaC templates."""
    templates: List[IaCTemplate] = Field(default_factory=list)
    deployment_order: List[str] = Field(default_factory=list)
    total_resources: int = 0


# =============================================================================
# Validation Models
# =============================================================================

class ValidationCheck(BaseModel):
    """Result of a validation check."""
    check_name: str
    passed: bool
    message: Optional[str] = None


class ValidationReport(BaseModel):
    """Cross-validation report between sources."""
    status: str = Field(description="PASSED, PASSED_WITH_WARNINGS, FAILED")
    checks_passed: int = 0
    checks_warned: int = 0
    checks_failed: int = 0
    checks: List[ValidationCheck] = Field(default_factory=list)
    warnings: List[ValidationWarning] = Field(default_factory=list)
    confidence_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence by category: compute, database, api, overall"
    )


# =============================================================================
# Migration Phase Models
# =============================================================================

class MigrationPhase(BaseModel):
    """A phase in the migration approach."""
    phase: int
    name: str
    description: str
    components: List[str] = Field(default_factory=list)
    estimated_effort_weeks: int
    dependencies: List[str] = Field(default_factory=list)


# =============================================================================
# Response Models
# =============================================================================

class ArchitectureSummary(BaseModel):
    """Executive summary of architecture recommendations."""
    application_type: str = Field(
        description="api-driven, batch-processing, hybrid, event-driven"
    )
    primary_compute: str
    primary_database: Optional[str] = None
    api_required: bool
    overall_confidence: float = Field(ge=0, le=1)
    estimated_monthly_cost: float


class ArchitectureResponse(BaseModel):
    """Complete Architecture Recommender response."""
    success: bool
    job_id: str
    status: str
    source_path: str
    output_path: str
    error: Optional[str] = None
    duration_seconds: float = 0

    # Summary
    summary: ArchitectureSummary

    # Recommendations
    compute_recommendation: ComputeRecommendation
    database_recommendation: DatabaseRecommendation
    api_recommendation: APIRecommendation
    storage_recommendation: StorageRecommendation
    security_recommendation: SecurityRecommendation

    # Cost
    cost_estimate: CostEstimate

    # Validation
    validation_report: ValidationReport
    warnings: List[ValidationWarning] = Field(default_factory=list)

    # Traceability
    traceability: Traceability

    # IaC
    iac_templates: Optional[IaCOutput] = None

    # Migration approach
    migration_phases: List[MigrationPhase] = Field(default_factory=list)

    # Metadata
    java_analysis: Optional[JavaAnalysis] = None
    sources_used: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ArchitectureStatusResponse(BaseModel):
    """Status of an Architecture Recommender job."""
    job_id: str
    flow_type: str = "architecture"
    status: str
    output_path: Optional[str] = None
    created_at: str
    updated_at: str


class ArchitectureResultsResponse(BaseModel):
    """Results overview from Architecture Recommender."""
    job_id: str
    status: str
    output_path: str
    json_artifacts: List[str] = Field(default_factory=list)
    summary: ArchitectureSummary
