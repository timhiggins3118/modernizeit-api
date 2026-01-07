"""
Roadmap Generator

Creates migration roadmap based on:
- Business process priorities
- Integration complexity
- Dependencies between components
- Risk-based wave planning

DESIGN DECISION: Phases are always generated (never empty).
Uses sensible defaults when data is sparse.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Standard phase structure
ROADMAP_PHASES = {
    'phase_1_foundation': {
        'name': 'Foundation',
        'description': 'Infrastructure setup and low-risk migrations',
        'duration_weeks': 8,
        'activities': [
            'AWS environment setup',
            'CI/CD pipeline configuration',
            'Security and compliance framework',
            'Monitoring and observability setup'
        ],
        'milestones': [
            'Cloud environment operational',
            'First migration pipeline validated'
        ]
    },
    'phase_2_quick_wins': {
        'name': 'Quick Wins',
        'description': 'Low-complexity, high-value migrations',
        'duration_weeks': 12,
        'activities': [
            'Migrate standalone batch programs',
            'Simple file processing workflows',
            'Non-critical utilities'
        ],
        'milestones': [
            'First production workload on AWS',
            'Team gains modernization experience'
        ]
    },
    'phase_3_core_migration': {
        'name': 'Core Business Logic',
        'description': 'High-value core business processes',
        'duration_weeks': 24,
        'activities': [
            'Core transaction processing',
            'Primary business workflows',
            'Database migrations'
        ],
        'milestones': [
            'Core systems operational on AWS',
            'Legacy dependencies reduced'
        ]
    },
    'phase_4_integration': {
        'name': 'Integration Modernization',
        'description': 'Complex integrations and data flows',
        'duration_weeks': 16,
        'activities': [
            'CICS to API Gateway migration',
            'MQ to SQS/EventBridge migration',
            'IMS to DynamoDB/DocumentDB migration'
        ],
        'milestones': [
            'All integration points modernized',
            'Legacy middleware retired'
        ]
    },
    'phase_5_optimization': {
        'name': 'Optimization & Cutover',
        'description': 'Performance tuning and final cutover',
        'duration_weeks': 8,
        'activities': [
            'Performance optimization',
            'Cost optimization',
            'Final cutover planning',
            'Mainframe decommissioning'
        ],
        'milestones': [
            'Mainframe fully decommissioned',
            'Modern architecture operational'
        ]
    }
}


class RoadmapGenerator:
    """
    Generate migration roadmap from discovery analysis.

    Creates actionable phases with:
    - Wave-based component grouping
    - Risk prioritization
    - Dependency ordering
    - Resource allocation
    """

    def generate(
        self,
        business_processes: Dict[str, Any],
        integration_points: Dict[str, Any],
        api_patterns: Dict[str, Any],
        roi_analysis: Dict[str, Any],
        customer_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive migration roadmap.

        Args:
            business_processes: From BusinessProcessExtractor
            integration_points: From IntegrationDetector
            api_patterns: From APIPatternAnalyzer
            roi_analysis: From ROICalculator
            customer_preferences: Optional migration preferences

        Returns:
            Complete roadmap with phases, waves, and recommendations
        """
        prefs = customer_preferences or {}

        # Analyze complexity for timeline adjustments
        complexity_profile = self._analyze_complexity(
            integration_points,
            business_processes
        )

        # Create phases (always 5 phases)
        phases = self._create_phases(
            business_processes,
            integration_points,
            complexity_profile,
            prefs
        )

        # Create waves within phases
        waves = self._create_waves(
            business_processes,
            integration_points
        )

        # Calculate timeline
        timeline = self._calculate_timeline(phases, prefs)

        # Resource recommendations
        resources = self._recommend_resources(
            complexity_profile,
            timeline
        )

        # Risk assessment
        risks = self._assess_risks(
            integration_points,
            business_processes
        )

        # Success criteria
        success_criteria = self._define_success_criteria(roi_analysis)

        return {
            'executive_summary': self._create_executive_summary(
                timeline, roi_analysis, complexity_profile
            ),
            'phases': phases,
            'migration_waves': waves,
            'timeline': timeline,
            'resource_requirements': resources,
            'risk_assessment': risks,
            'success_criteria': success_criteria,
            'recommended_approach': api_patterns.get(
                'aws_architecture_recommendation', {}
            ),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _analyze_complexity(
        self,
        integration_points: Dict,
        business_processes: Dict
    ) -> Dict[str, Any]:
        """Analyze overall complexity profile."""
        integrations = integration_points.get('integration_points', [])
        processes = business_processes.get('business_processes', [])

        # Count by complexity
        high_complexity = len([
            ip for ip in integrations
            if ip.get('modernization_recommendation', {}).get('complexity') == 'High'
        ])
        medium_complexity = len([
            ip for ip in integrations
            if ip.get('modernization_recommendation', {}).get('complexity') == 'Medium'
        ])
        low_complexity = len([
            ip for ip in integrations
            if ip.get('modernization_recommendation', {}).get('complexity') == 'Low'
        ])

        # High-value processes
        high_value = len([
            p for p in processes
            if p.get('business_value') == 'High'
        ])

        # Overall complexity score (0-100)
        total_integrations = max(len(integrations), 1)
        complexity_score = (
            (high_complexity * 100 + medium_complexity * 50 + low_complexity * 20) /
            total_integrations
        )

        # Classify
        if complexity_score >= 70:
            classification = 'High'
            timeline_multiplier = 1.3
        elif complexity_score >= 40:
            classification = 'Medium'
            timeline_multiplier = 1.0
        else:
            classification = 'Low'
            timeline_multiplier = 0.8

        return {
            'score': round(complexity_score, 1),
            'classification': classification,
            'timeline_multiplier': timeline_multiplier,
            'high_complexity_integrations': high_complexity,
            'medium_complexity_integrations': medium_complexity,
            'low_complexity_integrations': low_complexity,
            'high_value_processes': high_value
        }

    def _create_phases(
        self,
        business_processes: Dict,
        integration_points: Dict,
        complexity_profile: Dict,
        prefs: Dict
    ) -> List[Dict[str, Any]]:
        """Create the 5 standard phases with customization."""
        phases = []
        multiplier = complexity_profile['timeline_multiplier']

        for i, (phase_id, template) in enumerate(ROADMAP_PHASES.items(), 1):
            # Adjust duration based on complexity
            adjusted_duration = round(template['duration_weeks'] * multiplier)

            # Get components for this phase
            components = self._get_phase_components(
                phase_id,
                business_processes,
                integration_points
            )

            phases.append({
                'phase_number': i,
                'phase_id': phase_id,
                'name': template['name'],
                'description': template['description'],
                'duration_weeks': adjusted_duration,
                'activities': template['activities'],
                'milestones': template['milestones'],
                'components': components,
                'status': 'Not Started'
            })

        return phases

    def _get_phase_components(
        self,
        phase_id: str,
        business_processes: Dict,
        integration_points: Dict
    ) -> List[str]:
        """Get component names for a phase."""
        processes = business_processes.get('business_processes', [])
        integrations = integration_points.get('integration_points', [])

        components = []

        if phase_id == 'phase_1_foundation':
            # Foundation has no specific components
            components = ['AWS Infrastructure', 'CI/CD Pipeline', 'Security Framework']

        elif phase_id == 'phase_2_quick_wins':
            # Low-complexity, low-value processes
            for p in processes:
                if p.get('complexity') == 'Low' and p.get('business_value') in ['Low', 'Medium']:
                    components.append(p.get('name', 'Unknown'))

        elif phase_id == 'phase_3_core_migration':
            # High-value processes
            for p in processes:
                if p.get('business_value') == 'High':
                    components.append(p.get('name', 'Unknown'))

        elif phase_id == 'phase_4_integration':
            # Complex integrations
            for ip in integrations:
                if ip.get('modernization_recommendation', {}).get('complexity') in ['High', 'Medium']:
                    components.append(ip.get('system_name', 'Unknown'))

        elif phase_id == 'phase_5_optimization':
            components = ['Performance Tuning', 'Cost Optimization', 'Cutover Execution']

        return components[:10]  # Limit for readability

    def _create_waves(
        self,
        business_processes: Dict,
        integration_points: Dict
    ) -> List[Dict[str, Any]]:
        """Create migration waves based on risk and dependencies."""
        processes = business_processes.get('business_processes', [])

        # Sort by priority
        sorted_processes = sorted(
            processes,
            key=lambda x: (x.get('modernization_priority', 5), -x.get('confidence_score', 0))
        )

        # Group into waves of 3-5 components
        waves = []
        current_wave = []
        wave_number = 1

        for proc in sorted_processes:
            current_wave.append({
                'name': proc.get('name', 'Unknown'),
                'business_value': proc.get('business_value', 'Medium'),
                'complexity': proc.get('complexity', 'Medium'),
                'components': proc.get('components_involved', [])[:3]
            })

            if len(current_wave) >= 4:
                waves.append({
                    'wave_number': wave_number,
                    'wave_name': f"Wave {wave_number}",
                    'items': current_wave,
                    'estimated_duration_weeks': 6 if wave_number == 1 else 8
                })
                wave_number += 1
                current_wave = []

        # Don't forget remaining items
        if current_wave:
            waves.append({
                'wave_number': wave_number,
                'wave_name': f"Wave {wave_number}",
                'items': current_wave,
                'estimated_duration_weeks': 6
            })

        # Ensure at least one wave
        if not waves:
            waves.append({
                'wave_number': 1,
                'wave_name': 'Wave 1',
                'items': [{'name': 'Initial Migration', 'business_value': 'Medium', 'complexity': 'Low'}],
                'estimated_duration_weeks': 6
            })

        return waves

    def _calculate_timeline(
        self,
        phases: List[Dict],
        prefs: Dict
    ) -> Dict[str, Any]:
        """Calculate overall timeline."""
        total_weeks = sum(p['duration_weeks'] for p in phases)
        total_months = round(total_weeks / 4.33)

        # Calculate phase boundaries
        phase_timeline = []
        current_week = 0

        for phase in phases:
            phase_timeline.append({
                'phase': phase['name'],
                'start_week': current_week,
                'end_week': current_week + phase['duration_weeks'],
                'duration_weeks': phase['duration_weeks']
            })
            current_week += phase['duration_weeks']

        return {
            'total_weeks': total_weeks,
            'total_months': total_months,
            'phase_timeline': phase_timeline,
            'recommended_start': prefs.get('preferred_start_date', 'Q1 2025'),
            'estimated_completion': f"~{total_months} months from start"
        }

    def _recommend_resources(
        self,
        complexity_profile: Dict,
        timeline: Dict
    ) -> Dict[str, Any]:
        """Recommend resource allocation."""
        # Base team size on complexity
        base_size = 5
        if complexity_profile['classification'] == 'High':
            base_size = 8
        elif complexity_profile['classification'] == 'Low':
            base_size = 4

        return {
            'core_team_size': base_size,
            'recommended_roles': [
                {'role': 'Technical Lead', 'count': 1, 'skills': ['Java', 'AWS', 'COBOL knowledge']},
                {'role': 'Cloud Architect', 'count': 1, 'skills': ['AWS', 'Serverless', 'Containers']},
                {'role': 'Developers', 'count': base_size - 3, 'skills': ['Java', 'Spring Boot', 'AWS SDK']},
                {'role': 'QA Engineer', 'count': 1, 'skills': ['Testing', 'Automation']}
            ],
            'peak_team_size': base_size + 2,
            'peak_phase': 'Core Business Logic',
            'training_needed': [
                'AWS Serverless fundamentals',
                'COBOL modernization patterns',
                'Java/Spring Boot for legacy developers'
            ]
        }

    def _assess_risks(
        self,
        integration_points: Dict,
        business_processes: Dict
    ) -> List[Dict[str, Any]]:
        """Assess migration risks."""
        risks = []
        integrations = integration_points.get('integration_points', [])

        # Integration risks
        high_complexity = [
            ip for ip in integrations
            if ip.get('modernization_recommendation', {}).get('complexity') == 'High'
        ]

        if len(high_complexity) > 3:
            risks.append({
                'risk': 'High integration complexity',
                'severity': 'High',
                'description': f"{len(high_complexity)} high-complexity integrations detected",
                'mitigation': 'Consider phased integration migration with abstraction layers',
                'owner': 'Technical Lead'
            })

        # CICS specific risk
        cics_count = len([
            ip for ip in integrations
            if 'CICS' in ip.get('system_name', '').upper()
        ])

        if cics_count > 0:
            risks.append({
                'risk': 'CICS transaction complexity',
                'severity': 'Medium',
                'description': 'CICS transactions require careful state management in cloud',
                'mitigation': 'Map CICS programs to Lambda functions with proper session handling',
                'owner': 'Cloud Architect'
            })

        # Skills risk
        risks.append({
            'risk': 'COBOL expertise availability',
            'severity': 'Medium',
            'description': 'Legacy COBOL knowledge needed during migration',
            'mitigation': 'Document business logic before migration, pair programming',
            'owner': 'Technical Lead'
        })

        # Default risk if none found
        if not risks:
            risks.append({
                'risk': 'Standard migration risk',
                'severity': 'Low',
                'description': 'Normal risks associated with any migration project',
                'mitigation': 'Follow best practices, incremental deployment',
                'owner': 'Project Manager'
            })

        return risks

    def _define_success_criteria(
        self,
        roi_analysis: Dict
    ) -> List[Dict[str, Any]]:
        """Define success criteria based on ROI."""
        headline = roi_analysis.get('headline_metrics', {})

        return [
            {
                'criterion': 'Cost Reduction',
                'target': f"Achieve ${headline.get('annual_recurring_savings', 0):,}/year savings",
                'measurement': 'Compare pre/post infrastructure and maintenance costs',
                'milestone': 'Phase 5 completion'
            },
            {
                'criterion': 'Payback Achievement',
                'target': f"Break even within {headline.get('payback_months', 12)} months",
                'measurement': 'Track cumulative savings vs investment',
                'milestone': f"Month {headline.get('payback_months', 12)}"
            },
            {
                'criterion': 'System Performance',
                'target': 'Match or exceed mainframe transaction performance',
                'measurement': 'Transaction latency, throughput metrics',
                'milestone': 'Phase 3 completion'
            },
            {
                'criterion': 'Zero Data Loss',
                'target': '100% data integrity during migration',
                'measurement': 'Data validation checksums, reconciliation reports',
                'milestone': 'Each phase completion'
            }
        ]

    def _create_executive_summary(
        self,
        timeline: Dict,
        roi_analysis: Dict,
        complexity_profile: Dict
    ) -> Dict[str, Any]:
        """Create executive summary."""
        headline = roi_analysis.get('headline_metrics', {})

        return {
            'recommended_approach': 'Phased Migration with AI-Accelerated Code Conversion',
            'total_duration': f"{timeline['total_months']} months",
            'total_investment': f"${headline.get('total_investment', 0):,}",
            'five_year_savings': f"${headline.get('five_year_savings', 0):,}",
            'roi': f"{headline.get('five_year_roi_percent', 0):.0f}%",
            'payback_period': f"{headline.get('payback_months', 0)} months",
            'complexity_assessment': complexity_profile['classification'],
            'key_benefits': [
                'Eliminate COBOL skills shortage risk',
                'Reduce infrastructure costs by 85%+',
                'Enable cloud-native capabilities',
                'Improve development velocity'
            ]
        }


def generate_roadmap(
    business_processes: Dict[str, Any],
    integration_points: Dict[str, Any],
    api_patterns: Dict[str, Any],
    roi_analysis: Dict[str, Any],
    customer_preferences: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function for roadmap generation."""
    generator = RoadmapGenerator()
    return generator.generate(
        business_processes,
        integration_points,
        api_patterns,
        roi_analysis,
        customer_preferences
    )
