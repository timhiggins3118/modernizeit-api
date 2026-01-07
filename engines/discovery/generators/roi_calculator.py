"""
ROI Calculator - Real Industry Formulas

Calculates ROI using real industry benchmarks:
- Gartner IT Key Metrics Data 2024
- EPAM Mainframe Modernization ROI Guide
- SoftwareMining Cost Comparison
- AWS Mainframe Modernization Case Studies

DESIGN DECISION: All values have documented sources.
Customer-specific data overrides defaults when provided.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..utils.roi_config import (
    ROIConfig,
    DEFAULT_ROI_CONFIG,
    classify_metric,
    BENCHMARK_RANGES
)


@dataclass
class CodeMetrics:
    """Code metrics from analysis."""
    total_loc: int
    total_files: int
    high_complexity_files: int
    medium_complexity_files: int
    low_complexity_files: int


@dataclass
class ProcessMetrics:
    """Business process metrics."""
    high_value_processes: int
    medium_value_processes: int
    low_value_processes: int
    total_processes: int


class ROICalculator:
    """
    Calculate ROI for mainframe modernization.

    Uses real industry benchmarks with transparent assumptions.
    All formulas documented with sources.
    """

    def __init__(self, config: Optional[ROIConfig] = None):
        self.config = config or DEFAULT_ROI_CONFIG

    def calculate(
        self,
        code_metrics: CodeMetrics,
        process_metrics: ProcessMetrics,
        integration_points: Dict[str, Any],
        customer_inputs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive ROI analysis.

        Args:
            code_metrics: LOC, file counts, complexity breakdown
            process_metrics: Business process counts by value
            integration_points: Detected integrations (for effort estimation)
            customer_inputs: Optional customer-specific data (overrides defaults)

        Returns:
            Complete ROI analysis with 5-year projections
        """
        # Merge customer inputs with defaults
        inputs = self._merge_customer_inputs(customer_inputs or {})

        # Calculate each cost category
        dev_costs = self._calculate_development_costs(code_metrics, integration_points)
        infra_costs = self._calculate_infrastructure_costs(code_metrics, inputs)
        maint_costs = self._calculate_maintenance_costs(code_metrics, inputs)
        risk_value = self._calculate_risk_value(code_metrics, inputs)
        productivity = self._calculate_productivity_gains(process_metrics)

        # Calculate totals
        total_investment = dev_costs['ai_accelerated_cost']
        annual_savings = (
            infra_costs['annual_savings'] +
            maint_costs['annual_savings'] +
            productivity['annual_value']
        )

        # Multi-year projection
        projections = self._calculate_projections(
            total_investment,
            annual_savings,
            risk_value['annual_risk_avoided']
        )

        # Calculate headline metrics
        roi_percent = (
            (projections['cumulative_savings'][-1] - total_investment) /
            total_investment * 100
        ) if total_investment > 0 else 0

        payback_months = self._calculate_payback_months(
            total_investment,
            annual_savings + risk_value['annual_risk_avoided']
        )

        # Classify against benchmarks
        roi_classification = classify_metric('roi_percent', roi_percent)
        payback_classification = classify_metric('payback_months', payback_months)

        return {
            'headline_metrics': {
                'total_investment': total_investment,
                'five_year_savings': projections['cumulative_savings'][-1],
                'five_year_roi_percent': round(roi_percent, 1),
                'roi_classification': roi_classification,
                'payback_months': payback_months,
                'payback_classification': payback_classification,
                'annual_recurring_savings': annual_savings,
                'net_present_value': self._calculate_npv(
                    total_investment, annual_savings, 0.08
                )
            },
            'cost_breakdown': {
                'development_costs': dev_costs,
                'infrastructure_costs': infra_costs,
                'maintenance_costs': maint_costs,
                'risk_mitigation': risk_value,
                'productivity_gains': productivity
            },
            'yearly_projections': projections,
            'assumptions': self.config.to_assumptions_dict(),
            'customer_inputs_used': inputs,
            'benchmark_context': {
                'industry_avg_roi': f"{BENCHMARK_RANGES['roi_percent']['medium']}%",
                'industry_avg_payback': f"{BENCHMARK_RANGES['payback_months']['medium']} months",
                'your_vs_industry': self._compare_to_industry(roi_percent, payback_months)
            },
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _merge_customer_inputs(self, customer_inputs: Dict) -> Dict[str, Any]:
        """Merge customer inputs with defaults."""
        return {
            'current_mips': customer_inputs.get('current_mips'),
            'annual_mainframe_cost': customer_inputs.get('annual_mainframe_cost'),
            'cobol_developer_count': customer_inputs.get('cobol_developer_count', 5),
            'cobol_developer_salary': customer_inputs.get(
                'cobol_developer_salary',
                self.config.skills_risk.default_cobol_salary
            ),
            'discount_rate': customer_inputs.get('discount_rate', 0.08)
        }

    def _calculate_development_costs(
        self,
        code_metrics: CodeMetrics,
        integration_points: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate development/migration costs.

        Formula:
        - Manual Cost = LOC * cost_per_loc_manual
        - AI Cost = LOC * cost_per_loc_ai
        - Savings = Manual - AI

        Sources:
        - SoftwareMining: $0.26-$0.29/LOC for automated
        - Industry: $1.50-$5.00/LOC for manual
        """
        cfg = self.config.development
        loc = code_metrics.total_loc

        manual_cost = loc * cfg.cost_per_loc_manual
        ai_cost = loc * cfg.cost_per_loc_ai_automated

        # Adjust for integration complexity
        integrations = integration_points.get('integration_points', [])
        high_complexity = len([
            ip for ip in integrations
            if ip.get('modernization_recommendation', {}).get('complexity') == 'High'
        ])

        # Add 10% per high-complexity integration
        complexity_multiplier = 1 + (high_complexity * 0.10)
        ai_cost *= complexity_multiplier

        # Time estimates
        kloc = loc / 1000
        manual_days = kloc * cfg.days_per_kloc_manual
        ai_days = kloc * cfg.days_per_kloc_ai

        savings = manual_cost - ai_cost
        savings_percent = (savings / manual_cost * 100) if manual_cost > 0 else 0

        return {
            'manual_rewrite_cost': round(manual_cost),
            'ai_accelerated_cost': round(ai_cost),
            'savings': round(savings),
            'savings_percent': round(savings_percent, 1),
            'manual_duration_days': round(manual_days),
            'ai_duration_days': round(ai_days),
            'time_savings_days': round(manual_days - ai_days),
            'complexity_adjustment': f"{(complexity_multiplier - 1) * 100:.0f}%",
            'formula': 'LOC × cost_per_loc (adjusted for integration complexity)',
            'source': 'SoftwareMining, Industry Average'
        }

    def _calculate_infrastructure_costs(
        self,
        code_metrics: CodeMetrics,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate infrastructure cost savings.

        Formula:
        - If customer provides annual_mainframe_cost: use that
        - Else estimate from LOC: (LOC/10000) * MIPS_per_10k * cost_per_MIPS
        - AWS Cost = Mainframe Cost * aws_multiplier
        - Savings = Mainframe - AWS

        Sources:
        - Planet Mainframe: $1,600/MIPS/year
        - AWS Case Studies: 85-90% savings
        """
        cfg = self.config.infrastructure

        # Use customer data if available, else estimate
        if inputs.get('annual_mainframe_cost'):
            current_annual = inputs['annual_mainframe_cost']
            estimation_method = 'Customer provided'
        elif inputs.get('current_mips'):
            current_annual = inputs['current_mips'] * cfg.cost_per_mips_annual
            estimation_method = f"MIPS × ${cfg.cost_per_mips_annual:,.0f}"
        else:
            # Estimate from LOC
            estimated_mips = (code_metrics.total_loc / 10000) * cfg.mips_per_10k_loc
            current_annual = max(
                estimated_mips * cfg.cost_per_mips_annual,
                cfg.minimum_annual_infra_cost
            )
            estimation_method = 'Estimated from LOC'

        aws_annual = current_annual * cfg.aws_cost_multiplier
        annual_savings = current_annual - aws_annual
        savings_percent = ((1 - cfg.aws_cost_multiplier) * 100)

        return {
            'current_mainframe_annual': round(current_annual),
            'projected_aws_annual': round(aws_annual),
            'annual_savings': round(annual_savings),
            'savings_percent': savings_percent,
            'estimation_method': estimation_method,
            'formula': 'Mainframe Cost × (1 - aws_multiplier)',
            'source': 'Planet Mainframe, AWS Case Studies'
        }

    def _calculate_maintenance_costs(
        self,
        code_metrics: CodeMetrics,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate maintenance cost savings.

        Formula:
        - Legacy Maintenance = LOC * legacy_maintenance_per_loc
        - Modern Maintenance = LOC * modern_maintenance_per_loc
        - Savings = Legacy - Modern

        Sources:
        - Gartner: Legacy consumes 60-80% of IT budgets
        - COBOL developers cost 40% more than Java
        """
        cfg = self.config.maintenance
        loc = code_metrics.total_loc

        legacy_annual = loc * cfg.legacy_maintenance_per_loc
        modern_annual = loc * cfg.modern_maintenance_per_loc

        annual_savings = legacy_annual - modern_annual
        savings_percent = (
            (annual_savings / legacy_annual * 100) if legacy_annual > 0 else 0
        )

        # Developer cost analysis
        dev_count = inputs.get('cobol_developer_count', 5)
        dev_salary = inputs.get('cobol_developer_salary', cfg.cobol_salary_premium * 89000)
        java_equivalent_salary = dev_salary / cfg.cobol_salary_premium

        labor_savings = dev_count * (dev_salary - java_equivalent_salary)

        return {
            'legacy_annual': round(legacy_annual),
            'modern_annual': round(modern_annual),
            'annual_savings': round(annual_savings),
            'savings_percent': round(savings_percent, 1),
            'labor_savings_annual': round(labor_savings),
            'cobol_dev_count': dev_count,
            'cobol_salary_premium': f"{(cfg.cobol_salary_premium - 1) * 100:.0f}%",
            'formula': 'LOC × (legacy_rate - modern_rate)',
            'source': 'Gartner IT Key Metrics'
        }

    def _calculate_risk_value(
        self,
        code_metrics: CodeMetrics,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate risk mitigation value.

        Covers:
        - Skills shortage risk (COBOL developers aging out)
        - System stability risk (mainframe expertise)
        - Opportunity cost (stuck on legacy)

        Sources:
        - Kyndryl: 75% of orgs report COBOL skills shortage
        - Average COBOL programmer age ~60
        """
        cfg = self.config.skills_risk

        dev_count = inputs.get('cobol_developer_count', 5)
        dev_salary = inputs.get('cobol_developer_salary', cfg.default_cobol_salary)

        # Skills shortage premium: risk of 15% annual salary increase
        annual_skills_risk = dev_count * dev_salary * cfg.skills_shortage_risk_premium

        # Outage risk: 1 major outage per year, 4 hours avg
        outage_risk = cfg.mainframe_outage_cost_per_hour * 4

        total_annual_risk = annual_skills_risk + outage_risk

        return {
            'skills_shortage_risk_annual': round(annual_skills_risk),
            'system_stability_risk_annual': round(outage_risk),
            'annual_risk_avoided': round(total_annual_risk),
            'skills_shortage_context': '75% of organizations report COBOL skills shortage',
            'avg_cobol_programmer_age': 60,
            'formula': '(DevCount × Salary × RiskPremium) + OutageRisk',
            'source': 'Kyndryl, ZipRecruiter 2024'
        }

    def _calculate_productivity_gains(
        self,
        process_metrics: ProcessMetrics
    ) -> Dict[str, Any]:
        """
        Calculate productivity gains from modernization.

        Modern systems enable:
        - Faster development cycles
        - Better integration capabilities
        - Cloud-native features (auto-scaling, etc.)
        """
        cfg = self.config.productivity

        # Productivity gain per high-value process (capped)
        high_value = process_metrics.high_value_processes
        gain_percent = min(
            high_value * cfg.productivity_gain_per_process,
            cfg.max_productivity_gain
        )

        annual_value = cfg.annual_productivity_baseline * (gain_percent / 100)

        return {
            'productivity_gain_percent': gain_percent,
            'high_value_processes_count': high_value,
            'annual_value': round(annual_value),
            'enablers': [
                'Modern CI/CD pipelines',
                'Cloud-native auto-scaling',
                'Better developer tooling',
                'Easier integrations (REST APIs)'
            ],
            'formula': f"min({cfg.productivity_gain_per_process}% × HighValueProcesses, {cfg.max_productivity_gain}%)"
        }

    def _calculate_projections(
        self,
        initial_investment: float,
        annual_savings: float,
        annual_risk_avoided: float
    ) -> Dict[str, Any]:
        """Calculate multi-year projections."""
        years = self.config.projection_years
        total_annual = annual_savings + annual_risk_avoided

        cumulative = []
        yearly = []

        for year in range(1, years + 1):
            yearly_value = total_annual
            if year == 1:
                # First year: subtract investment
                cumulative.append(yearly_value - initial_investment)
            else:
                cumulative.append(cumulative[-1] + yearly_value)
            yearly.append(yearly_value)

        return {
            'years': list(range(1, years + 1)),
            'yearly_savings': yearly,
            'cumulative_savings': cumulative,
            'break_even_year': next(
                (i + 1 for i, c in enumerate(cumulative) if c > 0),
                None
            )
        }

    def _calculate_payback_months(
        self,
        investment: float,
        annual_savings: float
    ) -> int:
        """Calculate payback period in months."""
        if annual_savings <= 0:
            return 999  # Never

        monthly_savings = annual_savings / 12
        months = investment / monthly_savings

        return round(months)

    def _calculate_npv(
        self,
        investment: float,
        annual_savings: float,
        discount_rate: float
    ) -> int:
        """Calculate Net Present Value."""
        years = self.config.projection_years
        npv = -investment

        for year in range(1, years + 1):
            npv += annual_savings / ((1 + discount_rate) ** year)

        return round(npv)

    def _compare_to_industry(
        self,
        roi_percent: float,
        payback_months: int
    ) -> str:
        """Generate comparison to industry benchmarks."""
        roi_class = classify_metric('roi_percent', roi_percent)
        payback_class = classify_metric('payback_months', payback_months)

        if roi_class == 'excellent' and payback_class == 'excellent':
            return 'Significantly better than industry average'
        elif roi_class in ['excellent', 'above_average']:
            return 'Above industry average'
        elif roi_class == 'average':
            return 'In line with industry average'
        else:
            return 'Below industry average - review assumptions'


def calculate_roi(
    code_metrics: Dict[str, Any],
    process_metrics: Dict[str, Any],
    integration_points: Dict[str, Any],
    customer_inputs: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function for ROI calculation."""
    calculator = ROICalculator()

    cm = CodeMetrics(
        total_loc=code_metrics.get('total_loc', 0),
        total_files=code_metrics.get('total_files', 0),
        high_complexity_files=code_metrics.get('high_complexity_files', 0),
        medium_complexity_files=code_metrics.get('medium_complexity_files', 0),
        low_complexity_files=code_metrics.get('low_complexity_files', 0)
    )

    pm = ProcessMetrics(
        high_value_processes=process_metrics.get('high_value_processes', 0),
        medium_value_processes=process_metrics.get('medium_value_processes', 0),
        low_value_processes=process_metrics.get('low_value_processes', 0),
        total_processes=process_metrics.get('total_processes', 0)
    )

    return calculator.calculate(cm, pm, integration_points, customer_inputs)
