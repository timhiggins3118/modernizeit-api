"""
Monolith Identifier V2 - Results API Handler
Lambda: MonolithIdentifierV2ResultsAPI

Purpose: API handler for retrieving analysis results

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Results API Handler

    Input (from API Gateway):
    {
        "pathParameters": {
            "job_id": "miv2_job_5150_TestApp01_1759500000_abc123de"
        },
        "queryStringParameters": {
            "section": "all"  # or "static_analysis", "patterns", "modularity", "decomposition"
        }
    }

    Output:
    {
        "statusCode": 200,
        "body": "{\"job_id\": \"...\", \"data\": {...}}"
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - RESULTS API")
        print("=" * 80)

        # Get job_id from path parameters
        path_params = event.get('pathParameters', {})
        job_id = path_params.get('job_id')

        if not job_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing job_id in path'
                })
            }

        # Get section filter from query parameters
        query_params = event.get('queryStringParameters') or {}
        section_filter = query_params.get('section', 'all')

        print(f"Job ID: {job_id}, Section: {section_filter}")

        # Parse job_id to extract account and app
        parts = job_id.split('_')
        if len(parts) < 6 or not job_id.startswith('miv2_job_'):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid job_id format',
                    'expected': 'miv2_job_{account}_{app}_{timestamp}_{uuid}'
                })
            }

        scout_account_id = parts[2]
        application_name = parts[3]

        print(f"Account: {scout_account_id}, App: {application_name}")

        # Special handling for analysis_text - generate comprehensive markdown report
        if section_filter == 'analysis_text':
            markdown_report = generate_monolith_report(scout_account_id, application_name, job_id)

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'data': markdown_report
                }, indent=2)
            }

        # Read requested artifacts
        result_data = {}

        if section_filter in ['all', 'static_analysis']:
            static_data = read_artifact(scout_account_id, application_name, job_id, 'static_monolith_analysis.json')
            if static_data:
                result_data['static_analysis'] = static_data

        if section_filter in ['all', 'ai_analysis']:
            ai_data = read_artifact(scout_account_id, application_name, job_id, 'ai_pattern_analysis.json')
            if ai_data:
                result_data['ai_pattern_analysis'] = ai_data

        if section_filter in ['all', 'modularity']:
            modularity_data = read_artifact(scout_account_id, application_name, job_id, 'modularity_metrics.json')
            if modularity_data:
                result_data['modularity_metrics'] = modularity_data

        if section_filter in ['all', 'patterns']:
            patterns_data = read_artifact(scout_account_id, application_name, job_id, 'detected_patterns.json')
            if patterns_data:
                result_data['detected_patterns'] = patterns_data

        if section_filter in ['all', 'decomposition']:
            decomp_data = read_artifact(scout_account_id, application_name, job_id, 'decomposition_strategy.json')
            if decomp_data:
                result_data['decomposition_strategy'] = decomp_data

        if not result_data:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Results not found',
                    'job_id': job_id,
                    'message': 'Analysis may still be in progress or failed'
                })
            }

        # Build summary if returning all sections
        if section_filter == 'all' and result_data:
            summary = build_summary(result_data)
            result_data['summary'] = summary

        response_body = {
            'job_id': job_id,
            'section': section_filter,
            'data': result_data
        }

        print(f"Returning {len(result_data)} sections")

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body, indent=2)
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def generate_monolith_report(account_id: str, app_name: str, job_id: str) -> str:
    """
    Generate comprehensive monolith analysis report in markdown format
    """
    lines = []

    # Read all artifacts
    static_data = read_artifact(account_id, app_name, job_id, 'static_monolith_analysis.json') or {}
    ai_data = read_artifact(account_id, app_name, job_id, 'ai_pattern_analysis.json') or {}
    modularity_data = read_artifact(account_id, app_name, job_id, 'modularity_metrics.json') or {}
    patterns_data = read_artifact(account_id, app_name, job_id, 'detected_patterns.json') or {}
    decomp_data = read_artifact(account_id, app_name, job_id, 'decomposition_strategy.json') or {}

    # Header
    lines.append("# Monolith Analysis Report")
    lines.append("")
    lines.append(f"**Application:** {app_name}")
    lines.append(f"**Job ID:** {job_id}")
    lines.append(f"**Total Programs:** {static_data.get('total_programs', 0)}")
    lines.append(f"**Total Lines of Code:** {static_data.get('total_loc', 0):,}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"This monolith analysis examined **{static_data.get('total_programs', 0)} programs** ")
    lines.append(f"containing **{static_data.get('total_loc', 0):,} lines of code**. ")

    agg_metrics = modularity_data.get('aggregate_metrics', {})
    lines.append(f"The system has an overall modularity score of **{agg_metrics.get('average_modularity', 0):.2f}**.")
    lines.append("")

    lines.append("### Key Findings")
    lines.append(f"- **Average LOC per Program:** {static_data.get('average_loc', 0)}")
    lines.append(f"- **Average Complexity:** {static_data.get('average_complexity', 0)}")
    lines.append(f"- **Average Coupling:** {agg_metrics.get('average_coupling', 0):.3f}")
    lines.append(f"- **Average Cohesion:** {agg_metrics.get('average_cohesion', 0):.3f}")
    lines.append("")

    # God Programs
    god_programs = patterns_data.get('detected_patterns', {}).get('god_programs', [])
    if god_programs:
        lines.append(f"- **God Programs Detected:** {len(god_programs)}")

    # Tight Coupling
    tight_coupling = patterns_data.get('detected_patterns', {}).get('tight_coupling', [])
    if tight_coupling:
        lines.append(f"- **High Coupling Areas:** {len(tight_coupling)}")

    # Recommended Services
    microservices = decomp_data.get('recommended_microservices', [])
    if microservices:
        lines.append(f"- **Recommended Microservices:** {len(microservices)}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Static Analysis
    lines.append("## Static Code Analysis")
    lines.append("")

    size_dist = static_data.get('size_distribution', {})
    lines.append("### Size Distribution")
    lines.append(f"- **Small Programs (<300 LOC):** {size_dist.get('small', 0)}")
    lines.append(f"- **Medium Programs (300-1000 LOC):** {size_dist.get('medium', 0)}")
    lines.append(f"- **Large Programs (1000-3000 LOC):** {size_dist.get('large', 0)}")
    lines.append(f"- **God Programs (>3000 LOC):** {size_dist.get('god_programs', 0)}")
    lines.append("")

    # Show top complex programs
    programs = static_data.get('programs', [])
    if programs:
        sorted_programs = sorted(programs, key=lambda x: x.get('cyclomatic_complexity', 0), reverse=True)
        lines.append("### Most Complex Programs (Top 5)")
        lines.append("")
        for prog in sorted_programs[:5]:
            lines.append(f"#### {prog.get('program_name')}")
            lines.append(f"- **LOC:** {prog.get('loc', 0)}")
            lines.append(f"- **Cyclomatic Complexity:** {prog.get('cyclomatic_complexity', 0)}")
            lines.append(f"- **Size Category:** {prog.get('size_category', 'unknown')}")
            lines.append(f"- **Call Statements:** {prog.get('call_statements', 0)}")
            lines.append(f"- **File Operations:** {prog.get('file_operations', 0)}")
            lines.append(f"- **Database Operations:** {prog.get('database_operations', 0)}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # Detected Patterns
    lines.append("## Detected Anti-Patterns")
    lines.append("")

    detected = patterns_data.get('detected_patterns', {})

    # God Programs
    if god_programs:
        lines.append("### God Programs (Overly Large Components)")
        lines.append("")
        for gp in god_programs:
            lines.append(f"- **{gp.get('program_name')}**")
            lines.append(f"  - LOC: {gp.get('loc', 0):,}")
            lines.append(f"  - Complexity: {gp.get('complexity', 0)}")
            lines.append(f"  - Recommendation: {gp.get('recommendation', 'N/A')}")
        lines.append("")

    # Tight Coupling
    if tight_coupling:
        lines.append("### Tight Coupling Areas")
        lines.append("")
        for tc in tight_coupling[:5]:
            lines.append(f"- **{tc.get('program_name')}**")
            lines.append(f"  - Coupling Factor: {tc.get('coupling_factor', 0):.3f}")
            lines.append(f"  - Fan-in: {tc.get('fan_in', 0)}, Fan-out: {tc.get('fan_out', 0)}")
            lines.append(f"  - Impact: {tc.get('impact', 'N/A')}")
        lines.append("")

    # Shared Data Hotspots
    shared_data = detected.get('shared_data_hotspots', [])
    if shared_data:
        lines.append("### Shared Data Hotspots")
        lines.append("")
        for sd in shared_data[:5]:
            lines.append(f"- **{sd.get('resource_name')}**")
            lines.append(f"  - Programs Using: {sd.get('program_count', 0)}")
            lines.append(f"  - Risk: {sd.get('risk_level', 'N/A')}")
        lines.append("")

    # Circular Dependencies
    circular = detected.get('circular_dependencies', [])
    if circular:
        lines.append("### Circular Dependencies")
        lines.append("")
        for circ in circular:
            cycle = circ.get('cycle', [])
            lines.append(f"- **{' → '.join(cycle)}**")
            lines.append(f"  - Severity: {circ.get('severity', 'N/A')}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Modularity Metrics
    lines.append("## Modularity Assessment")
    lines.append("")
    lines.append(f"**Overall Modularity Score:** {agg_metrics.get('average_modularity', 0):.2f}/10")
    lines.append("")
    lines.append("### Aggregate Metrics")
    lines.append(f"- **Average Coupling:** {agg_metrics.get('average_coupling', 0):.3f}")
    lines.append(f"- **Average Cohesion:** {agg_metrics.get('average_cohesion', 0):.3f}")
    lines.append(f"- **High Coupling Programs:** {agg_metrics.get('high_coupling_count', 0)}")
    lines.append(f"- **Low Cohesion Programs:** {agg_metrics.get('low_cohesion_count', 0)}")
    lines.append("")

    # Program-level modularity
    prog_metrics = modularity_data.get('by_program', [])
    if prog_metrics:
        # Show worst modularity programs
        sorted_mod = sorted(prog_metrics, key=lambda x: x.get('modularity_score', 10))
        lines.append("### Programs Needing Refactoring (Lowest Modularity)")
        lines.append("")
        for pm in sorted_mod[:5]:
            lines.append(f"- **{pm.get('program_name')}**")
            lines.append(f"  - Modularity Score: {pm.get('modularity_score', 0):.2f}/10")
            lines.append(f"  - Coupling: {pm.get('coupling_factor', 0):.3f}")
            lines.append(f"  - Cohesion: {pm.get('cohesion_score', 0):.3f}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Decomposition Strategy
    lines.append("## Recommended Decomposition Strategy")
    lines.append("")

    approach = decomp_data.get('recommended_approach', 'N/A')
    lines.append(f"**Recommended Approach:** {approach}")
    lines.append("")

    # Microservices
    if microservices:
        lines.append("### Suggested Microservices")
        lines.append("")
        for ms in microservices:
            lines.append(f"#### {ms.get('service_name')}")
            lines.append(f"- **Business Domain:** {ms.get('domain', 'N/A')}")
            lines.append(f"- **Programs:** {ms.get('program_count', 0)}")
            lines.append(f"- **Estimated LOC:** {ms.get('total_loc', 0):,}")
            lines.append(f"- **Internal Cohesion:** {ms.get('internal_cohesion', 0):.2f}")
            lines.append(f"- **External Coupling:** {ms.get('external_coupling', 0):.2f}")
            lines.append(f"- **Priority:** {ms.get('priority', 'N/A')}")

            programs_list = ms.get('programs', [])
            if programs_list:
                lines.append(f"- **Components ({len(programs_list)}):** {', '.join(programs_list[:3])}")
                if len(programs_list) > 3:
                    lines.append(f"  ... and {len(programs_list) - 3} more")

            lines.append("")

    # Refactoring Priorities
    refactor_priorities = decomp_data.get('refactoring_priorities', [])
    if refactor_priorities:
        lines.append("### Refactoring Priorities")
        lines.append("")
        for rp in refactor_priorities:
            lines.append(f"**Priority {rp.get('priority')}:** {rp.get('program_name')}")
            lines.append(f"- **Reason:** {rp.get('reason', 'N/A')}")
            lines.append(f"- **Estimated Effort:** {rp.get('estimated_effort_days', 0)} days")
            lines.append(f"- **Impact:** {rp.get('impact', 'N/A')}")
            lines.append("")

    # Migration Strategy
    migration = decomp_data.get('migration_strategy', {})
    if migration:
        lines.append("### Migration Strategy")
        lines.append("")
        lines.append(f"**Pattern:** {migration.get('pattern', 'N/A')}")
        lines.append(f"**Total Duration:** {migration.get('total_duration_weeks', 0)} weeks")
        lines.append(f"**Team Size:** {migration.get('recommended_team_size', 0)} people")
        lines.append("")

        phases = migration.get('phases', [])
        if phases:
            lines.append("**Phases:**")
            for phase in phases:
                lines.append(f"- **Phase {phase.get('phase')}:** {phase.get('name')} ({phase.get('duration_weeks', 0)} weeks)")
                components = phase.get('components', [])
                if components:
                    lines.append(f"  - Components: {len(components)}")
            lines.append("")

    # AI Insights
    if ai_data:
        insights = ai_data.get('ai_insights', {})
        if insights:
            lines.append("---")
            lines.append("")
            lines.append("## AI-Generated Insights")
            lines.append("")

            assessment = insights.get('monolith_assessment', '')
            if assessment:
                lines.append(f"**Assessment:** {assessment}")
                lines.append("")

            recommendations = insights.get('recommendations', [])
            if recommendations:
                lines.append("**Key Recommendations:**")
                for rec in recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by Cobalt ETL Studio - Monolith Identifier V2*")

    return "\n".join(lines)


def read_artifact(account_id: str, app_name: str, job_id: str, artifact_name: str) -> Dict[str, Any]:
    """Read an artifact from S3"""
    try:
        key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/{artifact_name}"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except s3_client.exceptions.NoSuchKey:
        print(f"Artifact not found: {artifact_name}")
        return None
    except Exception as e:
        print(f"Error reading {artifact_name}: {str(e)}")
        return None


def build_summary(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build summary from all result sections"""
    summary = {}

    # From static analysis
    if 'static_analysis' in result_data:
        static = result_data['static_analysis']
        summary['total_programs'] = static.get('total_programs', 0)
        summary['total_loc'] = static.get('total_loc', 0)
        summary['average_loc_per_program'] = static.get('average_loc', 0)

    # From patterns
    if 'detected_patterns' in result_data:
        patterns = result_data['detected_patterns']
        summary['god_programs'] = len(patterns.get('detected_patterns', {}).get('god_programs', []))
        summary['high_coupling'] = len(patterns.get('detected_patterns', {}).get('tight_coupling', []))
        summary['shared_data_hotspots'] = len(patterns.get('detected_patterns', {}).get('shared_data_hotspots', []))

    # From modularity
    if 'modularity_metrics' in result_data:
        modularity = result_data['modularity_metrics']
        agg = modularity.get('aggregate_metrics', {})
        summary['average_coupling'] = agg.get('average_coupling', 0)
        summary['average_cohesion'] = agg.get('average_cohesion', 0)
        summary['modularity_score'] = agg.get('average_modularity', 0)

    # From decomposition
    if 'decomposition_strategy' in result_data:
        decomp = result_data['decomposition_strategy']
        summary['recommended_microservices'] = len(decomp.get('recommended_microservices', []))
        summary['refactoring_priorities'] = len(decomp.get('refactoring_priorities', []))
        migration = decomp.get('migration_strategy', {})
        summary['estimated_migration_weeks'] = migration.get('total_duration_weeks', 0)

    return summary
