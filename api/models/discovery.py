"""
Discovery API Models

Pydantic models for Discovery flow - executive-facing business intelligence.
Target audience: CFO, CIO, VP Engineering (NOT developers)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================

class CustomerInputs(BaseModel):
    """
    Optional customer-provided data for more accurate ROI.
    If not provided, industry defaults are used.
    """
    current_mips: Optional[int] = Field(
        default=None,
        description="Current mainframe MIPS capacity (if known)"
    )
    annual_mainframe_cost: Optional[int] = Field(
        default=None,
        description="Current annual mainframe cost in USD (if known)"
    )
    cobol_developer_count: Optional[int] = Field(
        default=None,
        description="Number of COBOL developers on staff"
    )
    cobol_developer_salary: Optional[int] = Field(
        default=124681,
        description="Average COBOL developer salary (default: industry average $124,681)"
    )


class DiscoveryRequest(BaseModel):
    """Request to start Discovery analysis."""
    scout_account_id: str = Field(..., description="Customer account ID")
    application_name: str = Field(..., description="Application name")
    customer_inputs: Optional[CustomerInputs] = Field(
        default=None,
        description="Optional customer-provided data for more accurate ROI"
    )


# =============================================================================
# Response Models
# =============================================================================

class DiscoveryResponse(BaseModel):
    """Response from Discovery analysis."""
    success: bool
    job_id: str
    status: str
    source_path: str
    artifacts_path: str
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, str] = Field(default_factory=dict)


class DiscoveryStatusResponse(BaseModel):
    """Status of a Discovery job."""
    job_id: str
    flow_type: str
    status: str
    artifacts_path: Optional[str] = None
    created_at: str
    updated_at: str


class DiscoveryResultsResponse(BaseModel):
    """Results overview from Discovery."""
    job_id: str
    status: str
    artifacts_path: str
    json_artifacts: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# ROI Analysis Models
# =============================================================================

class DevelopmentCostAnalysis(BaseModel):
    """Development cost comparison: traditional vs AI-accelerated."""
    traditional_approach_cost: int = Field(
        description="Cost of manual COBOL rewrite ($1.50-$5.00/LOC)"
    )
    ai_accelerated_approach_cost: int = Field(
        description="Cost with AI-accelerated migration ($0.26-$0.29/LOC)"
    )
    cost_savings: int = Field(description="Savings from AI approach")
    savings_percent: float = Field(description="Percentage saved")


class TimeSavingsAnalysis(BaseModel):
    """Time-to-market improvement analysis."""
    traditional_development_days: int = Field(
        description="Days for manual rewrite (50 days/KLOC)"
    )
    ai_accelerated_development_days: int = Field(
        description="Days with AI (10 days/KLOC)"
    )
    time_savings_days: int
    time_savings_months: float
    time_to_market_improvement_percent: float


class InfrastructureSavingsAnalysis(BaseModel):
    """Infrastructure cost comparison: mainframe vs AWS."""
    annual_legacy_cost: int = Field(
        description="Annual mainframe cost ($1,600/MIPS)"
    )
    annual_aws_cost: int = Field(
        description="Annual AWS cost (typically 15-50% of mainframe)"
    )
    annual_savings: int
    savings_5_years: int
    savings_percent: float


class MaintenanceSavingsAnalysis(BaseModel):
    """Maintenance cost comparison: legacy vs modern."""
    annual_legacy_maintenance: int = Field(
        description="Legacy maintenance ($3.50/LOC/year + COBOL premium)"
    )
    annual_modern_maintenance: int = Field(
        description="Modern maintenance ($1.00/LOC/year)"
    )
    annual_savings: int
    savings_5_years: int
    reduction_percent: float


class ProductivityGainsAnalysis(BaseModel):
    """Productivity improvements from modernization."""
    high_value_business_processes: int
    productivity_gain_percent: float
    annual_productivity_gain: int
    productivity_gains_5_years: int


class RiskAnalysis(BaseModel):
    """Risk reduction value from eliminating mainframe dependency."""
    skills_shortage_risk_value: int = Field(
        description="Cost of COBOL talent scarcity (avg age ~60, 75% report shortage)"
    )
    mainframe_dependency_risk_value: int = Field(
        description="Value of eliminating single point of failure"
    )
    total_risk_reduction_value: int
    risk_factors: List[str] = Field(default_factory=list)


class ROISummary(BaseModel):
    """Executive summary of ROI analysis."""
    total_investment: int = Field(description="Total modernization investment")
    total_savings_5_years: int = Field(description="5-year total savings")
    roi_percent: float = Field(description="Return on investment percentage")
    payback_period_months: float = Field(description="Months to break even")


class ROIAnalysis(BaseModel):
    """Complete ROI analysis with industry benchmarks."""
    summary: ROISummary
    development_cost_analysis: DevelopmentCostAnalysis
    time_savings_analysis: TimeSavingsAnalysis
    infrastructure_savings_analysis: InfrastructureSavingsAnalysis
    maintenance_savings_analysis: MaintenanceSavingsAnalysis
    productivity_gains_analysis: ProductivityGainsAnalysis
    risk_analysis: RiskAnalysis
    assumptions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Assumptions used in calculations (for transparency)"
    )
    generated_at: Optional[str] = None
    source_job_id: Optional[str] = None


# =============================================================================
# Business Process Models
# =============================================================================

class BusinessProcess(BaseModel):
    """A discovered business process/capability."""
    process_id: str
    process_name: str
    description: str
    business_value: str = Field(description="High/Medium/Low")
    complexity: str = Field(description="High/Medium/Low")
    execution_frequency: str = Field(description="Real-time/Batch/Daily/Weekly")
    confidence_score: int = Field(ge=0, le=100)
    cloud_readiness_score: int = Field(ge=0, le=100)
    business_domain: str
    criticality: str
    modernization_priority: int = Field(ge=1, le=5)
    recommended_approach: str
    components_involved: List[str] = Field(default_factory=list)
    aws_recommendations: List[str] = Field(default_factory=list)


class BusinessProcessesSummary(BaseModel):
    """Summary of discovered business processes."""
    total_processes: int
    high_value_processes: int
    medium_value_processes: int
    low_value_processes: int
    real_time_processes: int
    batch_processes: int
    average_confidence_score: float
    average_cloud_readiness: float


class BusinessProcessesOutput(BaseModel):
    """Business processes discovery output."""
    business_processes: List[BusinessProcess]
    summary: BusinessProcessesSummary
    generated_at: Optional[str] = None
    source_job_id: Optional[str] = None


# =============================================================================
# Integration Points Models
# =============================================================================

class ModernizationRecommendation(BaseModel):
    """AWS modernization recommendation for an integration."""
    aws_service: str = Field(description="Recommended AWS service")
    migration_approach: str = Field(description="Migration strategy")
    estimated_effort_weeks: int
    complexity: str = Field(description="High/Medium/Low")
    rationale: str


class IntegrationPoint(BaseModel):
    """A detected integration point (CICS, DB2, MQ, VSAM, etc.)."""
    integration_id: str
    integration_type: str = Field(
        description="Database/Transaction Manager/Messaging/File System"
    )
    system_name: str = Field(description="DB2/CICS/MQ/VSAM/etc.")
    description: str
    access_pattern: str
    detected_evidence: List[str] = Field(
        default_factory=list,
        description="Code patterns that detected this integration"
    )
    programs_using: List[str] = Field(default_factory=list)
    modernization_recommendation: ModernizationRecommendation


class IntegrationPointsSummary(BaseModel):
    """Summary of detected integrations."""
    total_integration_points: int
    by_type: Dict[str, int] = Field(default_factory=dict)
    high_complexity_count: int
    medium_complexity_count: int
    low_complexity_count: int


class IntegrationPointsOutput(BaseModel):
    """Integration points detection output."""
    integration_points: List[IntegrationPoint]
    summary: IntegrationPointsSummary
    generated_at: Optional[str] = None
    source_job_id: Optional[str] = None


# =============================================================================
# API Pattern Models
# =============================================================================

class AWSArchitectureRecommendation(BaseModel):
    """Recommended AWS architecture based on execution patterns."""
    primary_service: str
    supporting_services: List[str] = Field(default_factory=list)
    architecture_pattern: str
    estimated_cost_monthly: str
    scalability: str
    complexity: str
    rationale: str


class APIPatternOutput(BaseModel):
    """API/execution pattern analysis output."""
    primary_api_pattern: str = Field(
        description="real_time_transaction/batch_processing/event_driven/hybrid"
    )
    pattern_distribution: Dict[str, float] = Field(
        default_factory=dict,
        description="Percentage of each pattern type"
    )
    pattern_details: List[Dict[str, Any]] = Field(default_factory=list)
    aws_architecture_recommendation: AWSArchitectureRecommendation
    generated_at: Optional[str] = None
    source_job_id: Optional[str] = None


# =============================================================================
# Migration Roadmap Models
# =============================================================================

class RoadmapComponent(BaseModel):
    """A component to be migrated in a phase."""
    component: str
    programs: List[str] = Field(default_factory=list)
    modernization_approach: str
    rationale: str
    estimated_effort_weeks: int
    estimated_cost_usd: int


class RoadmapRisk(BaseModel):
    """A risk associated with a migration phase."""
    risk: str
    mitigation: str
    severity: str = Field(description="High/Medium/Low")


class RoadmapPhase(BaseModel):
    """A phase in the migration roadmap."""
    phase: int
    name: str
    duration_months: int
    start_month: int
    end_month: int
    components: List[RoadmapComponent]
    deliverables: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    risks: List[RoadmapRisk] = Field(default_factory=list)
    cost_usd: int


class KeyRisk(BaseModel):
    """A key risk for the overall migration."""
    category: str
    description: str
    mitigation: str


class MigrationRoadmap(BaseModel):
    """Complete migration roadmap."""
    recommended_approach: str
    overall_duration_months: int
    total_estimated_cost_usd: int
    migration_strategy: str
    phases: List[RoadmapPhase]
    success_factors: List[str] = Field(default_factory=list)
    key_risks: List[KeyRisk] = Field(default_factory=list)
    generated_at: Optional[str] = None
    source_job_id: Optional[str] = None
