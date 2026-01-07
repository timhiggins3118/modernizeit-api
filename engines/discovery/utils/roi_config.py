"""
ROI Configuration - Industry Benchmarks

All values sourced from industry research (2024-2025):
- Gartner IT Key Metrics Data 2024
- EPAM Mainframe Modernization ROI Guide
- SoftwareMining Cost Comparison
- AWS Mainframe Modernization Case Studies
- Kyndryl Mainframe Skills Gap Report

These are DEFAULTS - can be overridden with customer-specific data.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class DevelopmentCostParams:
    """
    Development cost parameters.

    Sources:
    - SoftwareMining: $0.26-$0.29/LOC for automated migration
    - Industry average: $1.50-$5.00/LOC for manual rewrite
    - FairCom: Claims 80% savings with modernization tools
    """

    # Cost per line of code
    cost_per_loc_manual: float = 3.00       # Manual COBOL rewrite (conservative middle)
    cost_per_loc_ai_automated: float = 0.28  # AI-accelerated migration

    # Time per 1000 lines of code (days)
    days_per_kloc_manual: float = 50.0      # Manual rewrite
    days_per_kloc_ai: float = 10.0          # AI-accelerated

    # Developer day cost
    developer_day_cost: int = 800           # Blended rate


@dataclass
class InfrastructureCostParams:
    """
    Infrastructure cost parameters.

    Sources:
    - Planet Mainframe: $1,600/MIPS/year for large mainframes
    - AWS Case Study: 85-90% savings vs mainframe
    - Microsoft: 1 x86 core ≈ 150 MIPS
    """

    # Mainframe costs
    cost_per_mips_annual: float = 1600.0    # $/MIPS/year
    mips_per_10k_loc: float = 1.0           # Estimate: 1 MIPS per 10K LOC

    # AWS costs as percentage of mainframe
    aws_cost_multiplier: float = 0.15       # AWS = 15% of mainframe (85% savings)

    # Minimum infrastructure cost (for small applications)
    minimum_annual_infra_cost: int = 50000


@dataclass
class MaintenanceCostParams:
    """
    Maintenance cost parameters.

    Sources:
    - Gartner: Legacy maintenance consumes 60-80% of IT budgets
    - Industry: COBOL developers cost 40% more than Java developers
    """

    # Per LOC annual maintenance
    legacy_maintenance_per_loc: float = 3.50   # Legacy COBOL
    modern_maintenance_per_loc: float = 1.00   # Modern Java/cloud

    # COBOL developer premium
    cobol_salary_premium: float = 1.4          # 40% higher than Java devs


@dataclass
class SkillsRiskParams:
    """
    Skills shortage risk parameters.

    Sources:
    - ZipRecruiter 2024: Median COBOL salary $112,558
    - Comparably: Average $124,681
    - Kyndryl: 75% of orgs report COBOL skills shortage
    - Industry: Average COBOL programmer age ~60
    """

    # Default COBOL developer salary
    default_cobol_salary: int = 124681

    # Risk premium for skills shortage
    skills_shortage_risk_premium: float = 0.15  # 15% annual cost increase risk

    # Mainframe outage cost
    mainframe_outage_cost_per_hour: int = 100000


@dataclass
class ProductivityParams:
    """Productivity gain parameters."""

    # Productivity gain per high-value process modernized
    productivity_gain_per_process: float = 5.0  # 5% per process, cap at 50%
    max_productivity_gain: float = 50.0         # Cap at 50%

    # Annual baseline productivity value
    annual_productivity_baseline: int = 100000


@dataclass
class ROIConfig:
    """
    Complete ROI configuration with all parameters.

    DESIGN DECISION: We use industry defaults but allow override.
    This enables:
    1. Quick estimates without customer data
    2. Accurate projections with customer data
    3. Transparent assumptions (all values documented)
    """

    development: DevelopmentCostParams = field(default_factory=DevelopmentCostParams)
    infrastructure: InfrastructureCostParams = field(default_factory=InfrastructureCostParams)
    maintenance: MaintenanceCostParams = field(default_factory=MaintenanceCostParams)
    skills_risk: SkillsRiskParams = field(default_factory=SkillsRiskParams)
    productivity: ProductivityParams = field(default_factory=ProductivityParams)

    # Time horizon for projections
    projection_years: int = 5

    def to_assumptions_dict(self) -> Dict[str, Any]:
        """
        Return all assumptions as a dictionary for transparency.
        This is included in ROI output so executives know the basis.
        """
        return {
            'development_costs': {
                'manual_rewrite_per_loc': f"${self.development.cost_per_loc_manual:.2f}",
                'ai_automated_per_loc': f"${self.development.cost_per_loc_ai_automated:.2f}",
                'manual_days_per_kloc': self.development.days_per_kloc_manual,
                'ai_days_per_kloc': self.development.days_per_kloc_ai,
                'source': 'SoftwareMining, Industry Average'
            },
            'infrastructure_costs': {
                'mainframe_per_mips_annual': f"${self.infrastructure.cost_per_mips_annual:,.0f}",
                'aws_savings_percent': f"{(1 - self.infrastructure.aws_cost_multiplier) * 100:.0f}%",
                'source': 'Planet Mainframe, AWS Case Studies'
            },
            'maintenance_costs': {
                'legacy_per_loc_annual': f"${self.maintenance.legacy_maintenance_per_loc:.2f}",
                'modern_per_loc_annual': f"${self.maintenance.modern_maintenance_per_loc:.2f}",
                'cobol_salary_premium': f"{(self.maintenance.cobol_salary_premium - 1) * 100:.0f}%",
                'source': 'Gartner IT Key Metrics'
            },
            'skills_risk': {
                'avg_cobol_salary': f"${self.skills_risk.default_cobol_salary:,}",
                'skills_shortage_risk': f"{self.skills_risk.skills_shortage_risk_premium * 100:.0f}%",
                'source': 'ZipRecruiter 2024, Kyndryl'
            },
            'projection_period': f"{self.projection_years} years"
        }


# Default configuration instance
DEFAULT_ROI_CONFIG = ROIConfig()


# =============================================================================
# Industry Benchmark Ranges (for validation and reporting)
# =============================================================================

BENCHMARK_RANGES = {
    'roi_percent': {
        'low': 50,
        'medium': 100,
        'high': 300,
        'description': '5-year ROI percentage'
    },
    'payback_months': {
        'low': 18,
        'medium': 10,
        'high': 6,
        'description': 'Months to break even (lower is better)'
    },
    'infrastructure_savings_percent': {
        'low': 50,
        'medium': 75,
        'high': 90,
        'description': 'Annual infrastructure cost reduction'
    },
    'development_savings_percent': {
        'low': 60,
        'medium': 77,
        'high': 85,
        'description': 'Development cost reduction with AI'
    },
    'maintenance_savings_percent': {
        'low': 30,
        'medium': 45,
        'high': 60,
        'description': 'Annual maintenance cost reduction'
    }
}


def classify_metric(metric_name: str, value: float) -> str:
    """
    Classify a metric value against industry benchmarks.

    Returns: 'below_average', 'average', 'above_average', 'excellent'
    """
    if metric_name not in BENCHMARK_RANGES:
        return 'unknown'

    ranges = BENCHMARK_RANGES[metric_name]

    # For payback months, lower is better (invert logic)
    if metric_name == 'payback_months':
        if value <= ranges['high']:
            return 'excellent'
        elif value <= ranges['medium']:
            return 'above_average'
        elif value <= ranges['low']:
            return 'average'
        else:
            return 'below_average'
    else:
        # For other metrics, higher is better
        if value >= ranges['high']:
            return 'excellent'
        elif value >= ranges['medium']:
            return 'above_average'
        elif value >= ranges['low']:
            return 'average'
        else:
            return 'below_average'
