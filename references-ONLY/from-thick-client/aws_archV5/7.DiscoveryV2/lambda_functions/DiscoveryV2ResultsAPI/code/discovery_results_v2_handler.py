"""
Discovery V2 - Results API Handler
Lambda: DiscoveryV2ResultsAPI

API Endpoint: GET /resultsdv2/{job_id}
Purpose: Retrieve discovery results

V2 Design Principles:
- Supports section filtering via query parameters
- Returns comprehensive discovery report
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from typing import Dict, Any, Optional

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Retrieve Discovery Results

    Input (API Gateway GET):
    Path: /resultsdv2/{job_id}
    Query params (optional):
    - ?section=summary
    - ?section=business_processes
    - ?section=integration_points
    - ?section=api_patterns
    - ?section=roi_analysis
    - ?section=roadmap

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "section": "all" or specific section,
        "data": { ... comprehensive results ... }
    }
    """
    try:
        # Extract job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing job_id in path'
                })
            }

        # Validate job_id format
        if not job_id.startswith('dv2_job_'):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid job_id format. Must start with dv2_job_'
                })
            }

        # Parse job_id
        parts = job_id.split('_')
        if len(parts) < 5:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid job_id format'
                })
            }

        scout_account_id = parts[2]
        application_name = parts[3]

        # Get section filter (if any)
        query_params = event.get('queryStringParameters') or {}
        section = query_params.get('section', 'all')

        # Check if job is completed
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"

        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read())

            if status_data.get('state') != 'completed':  # Step Functions uses 'state' not 'status'
                return {
                    'statusCode': 202,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'message': 'Job not yet completed',
                        'status': status_data.get('state'),
                        'progress': status_data.get('progress'),
                        'check_status_url': f"/statusdv2/{job_id}"
                    })
                }
        except s3_client.exceptions.NoSuchKey:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Job not found',
                    'job_id': job_id
                })
            }

        # Read results based on section
        artifacts_prefix = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/"

        # Special handling for analysis_text - generate comprehensive markdown report
        if section == 'analysis_text':
            markdown_report = generate_discovery_report(artifacts_prefix, job_id, application_name)

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'data': markdown_report
                }, indent=2)
            }

        results = {}

        # NEW: If specific section filter requested, return ONLY that data (UI-friendly)
        if section != 'all' and section != 'summary':
            filtered_data = extract_section(artifacts_prefix, section)
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'data': filtered_data
                }, indent=2)
            }

        # EXISTING: Return all or summary (keeps current behavior)
        if section == 'all' or section == 'summary':
            results['summary'] = read_summary(artifacts_prefix)

        if section == 'all' or section == 'business_processes':
            results['business_processes'] = read_json_file(f"{artifacts_prefix}business_processes.json")

        if section == 'all' or section == 'integration_points':
            results['integration_points'] = read_json_file(f"{artifacts_prefix}integration_points.json")

        if section == 'all' or section == 'api_patterns':
            results['api_patterns'] = read_json_file(f"{artifacts_prefix}api_patterns.json")

        if section == 'all' or section == 'roi_analysis':
            results['roi_analysis'] = read_json_file(f"{artifacts_prefix}roi_analysis.json")

        if section == 'all' or section == 'roadmap':
            results['roadmap'] = read_json_file(f"{artifacts_prefix}migration_roadmap.json")

        # Build response (keeps existing format)
        response_data = {
            'job_id': job_id,
            'section': section,
            'data': results
        }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_data, indent=2)
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2ResultsAPI: {str(e)}")
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


def generate_discovery_report(artifacts_prefix: str, job_id: str, application_name: str) -> str:
    """
    Generate comprehensive discovery report in markdown format
    Similar to V1 but leveraging V2's richer data
    """
    lines = []

    # Read all artifacts
    summary_data = read_summary(artifacts_prefix)
    bp_data = read_json_file(f"{artifacts_prefix}business_processes.json")
    int_data = read_json_file(f"{artifacts_prefix}integration_points.json")
    api_data = read_json_file(f"{artifacts_prefix}api_patterns.json")
    roi_data = read_json_file(f"{artifacts_prefix}roi_analysis.json")
    roadmap_data = read_json_file(f"{artifacts_prefix}migration_roadmap.json")

    # Header
    lines.append("# Application Discovery Report")
    lines.append("")
    lines.append(f"**Application:** {application_name}")
    lines.append(f"**Job ID:** {job_id}")
    lines.append(f"**Total Files Analyzed:** {summary_data.get('total_files_analyzed', 0)}")
    lines.append(f"**API Pattern:** {summary_data.get('api_pattern_detected', 'Unknown')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"This application analysis identified **{summary_data.get('business_processes_discovered', 0)} business processes** ")
    lines.append(f"across **{summary_data.get('total_files_analyzed', 0)} files**. ")
    lines.append(f"The modernization is estimated to take **{summary_data.get('migration_duration_months', 0)} months** ")
    lines.append(f"with a total investment of **${summary_data.get('total_migration_cost', 0):,}**.")
    lines.append("")
    lines.append("### Key Metrics")
    lines.append(f"- **ROI:** {summary_data.get('roi_percent', 0):.1f}%")
    lines.append(f"- **Payback Period:** {summary_data.get('payback_period_months', 0):.1f} months")
    lines.append(f"- **5-Year Savings:** ${summary_data.get('total_savings_5_years', 0):,}")
    lines.append(f"- **High-Value Processes:** {summary_data.get('high_value_processes', 0)}")
    lines.append(f"- **Integration Points:** {summary_data.get('integration_points_discovered', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Business Processes
    lines.append("## Business Processes Discovered")
    lines.append("")
    business_processes = bp_data.get('business_processes', [])
    if business_processes:
        for bp in business_processes:
            lines.append(f"### {bp.get('process_name')}")
            lines.append("")
            lines.append(f"**Description:** {bp.get('description')}")
            lines.append(f"**Business Value:** {bp.get('business_value')}")
            lines.append(f"**Complexity:** {bp.get('complexity')}")
            lines.append(f"**Execution Frequency:** {bp.get('execution_frequency')}")
            lines.append(f"**Business Domain:** {bp.get('business_domain')}")
            lines.append(f"**Criticality:** {bp.get('criticality')}")
            lines.append(f"**Modernization Priority:** {bp.get('modernization_priority')}")
            lines.append(f"**Recommended Approach:** {bp.get('recommended_approach')}")
            lines.append("")

            components = bp.get('components_involved', [])
            if components:
                lines.append(f"**Components ({len(components)}):**")
                for comp in components[:5]:  # Show first 5
                    lines.append(f"- {comp}")
                if len(components) > 5:
                    lines.append(f"- ... and {len(components) - 5} more")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Integration Points
    lines.append("## Integration Points")
    lines.append("")
    integration_points = int_data.get('integration_points', [])
    if integration_points:
        for ip in integration_points:
            lines.append(f"### {ip.get('system_name')} ({ip.get('integration_type')})")
            lines.append("")
            lines.append(f"**Description:** {ip.get('description')}")
            lines.append(f"**Access Pattern:** {ip.get('access_pattern')}")
            lines.append("")

            mod_rec = ip.get('modernization_recommendation', {})
            if mod_rec:
                lines.append("**Modernization Recommendation:**")
                lines.append(f"- **AWS Service:** {mod_rec.get('aws_service')}")
                lines.append(f"- **Approach:** {mod_rec.get('migration_approach')}")
                lines.append(f"- **Estimated Effort:** {mod_rec.get('estimated_effort_weeks')} weeks")
                lines.append(f"- **Complexity:** {mod_rec.get('complexity')}")
                lines.append("")

            programs = ip.get('programs_using', [])
            if programs:
                lines.append(f"**Programs Using ({len(programs)}):** {', '.join(programs[:3])}")
                if len(programs) > 3:
                    lines.append(f"... and {len(programs) - 3} more")
                lines.append("")

            lines.append("---")
            lines.append("")
    else:
        lines.append("No external integration points detected.")
        lines.append("")
        lines.append("---")
        lines.append("")

    # API Patterns & AWS Architecture
    lines.append("## API Pattern Analysis")
    lines.append("")
    lines.append(f"**Primary Pattern:** {api_data.get('primary_api_pattern', 'Unknown')}")
    lines.append("")

    pattern_dist = api_data.get('pattern_distribution', {})
    if pattern_dist:
        lines.append("**Pattern Distribution:**")
        for pattern, percent in pattern_dist.items():
            lines.append(f"- {pattern.replace('_', ' ').title()}: {percent:.1f}%")
        lines.append("")

    aws_rec = api_data.get('aws_architecture_recommendation', {})
    if aws_rec:
        lines.append("**AWS Architecture Recommendation:**")
        lines.append(f"- **Primary Service:** {aws_rec.get('primary_service')}")
        lines.append(f"- **Supporting Services:** {', '.join(aws_rec.get('supporting_services', []))}")
        lines.append(f"- **Architecture Pattern:** {aws_rec.get('architecture_pattern')}")
        lines.append(f"- **Estimated Monthly Cost:** {aws_rec.get('estimated_cost_monthly')}")
        lines.append(f"- **Scalability:** {aws_rec.get('scalability')}")
        lines.append(f"- **Complexity:** {aws_rec.get('complexity')}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ROI Analysis
    lines.append("## Return on Investment (ROI)")
    lines.append("")
    roi_summary = roi_data.get('summary', {})
    lines.append(f"- **Total Investment:** ${roi_summary.get('total_investment', 0):,}")
    lines.append(f"- **5-Year Savings:** ${roi_summary.get('total_savings_5_years', 0):,}")
    lines.append(f"- **ROI Percentage:** {roi_summary.get('roi_percent', 0):.1f}%")
    lines.append(f"- **Payback Period:** {roi_summary.get('payback_period_months', 0):.1f} months")
    lines.append("")

    # Development Cost Savings
    dev_cost = roi_data.get('development_cost_analysis', {})
    if dev_cost:
        lines.append("### Development Cost Savings (AI-Accelerated)")
        lines.append(f"- **Traditional Approach:** ${dev_cost.get('traditional_approach_cost', 0):,}")
        lines.append(f"- **AI-Accelerated Approach:** ${dev_cost.get('ai_accelerated_approach_cost', 0):,}")
        lines.append(f"- **Cost Savings:** ${dev_cost.get('cost_savings', 0):,} ({dev_cost.get('savings_percent', 0):.0f}%)")
        lines.append("")

    # Time Savings
    time_savings = roi_data.get('time_savings_analysis', {})
    if time_savings:
        lines.append("### Time-to-Market Improvement")
        lines.append(f"- **Traditional Development:** {time_savings.get('traditional_development_days', 0)} days")
        lines.append(f"- **AI-Accelerated Development:** {time_savings.get('ai_accelerated_development_days', 0)} days")
        lines.append(f"- **Time Savings:** {time_savings.get('time_savings_months', 0):.1f} months ({time_savings.get('time_to_market_improvement_percent', 0):.0f}%)")
        lines.append("")

    # Infrastructure Savings
    infra_savings = roi_data.get('infrastructure_savings_analysis', {})
    if infra_savings:
        lines.append("### Infrastructure Cost Savings")
        lines.append(f"- **Annual Legacy Cost:** ${infra_savings.get('annual_legacy_cost', 0):,}")
        lines.append(f"- **Annual AWS Cost:** ${infra_savings.get('annual_aws_cost', 0):,}")
        lines.append(f"- **Annual Savings:** ${infra_savings.get('annual_savings', 0):,}")
        lines.append(f"- **5-Year Savings:** ${infra_savings.get('savings_5_years', 0):,}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Migration Roadmap
    lines.append("## Modernization Roadmap")
    lines.append("")
    lines.append(f"**Recommended Approach:** {roadmap_data.get('recommended_approach', 'N/A')}")
    lines.append(f"**Overall Duration:** {roadmap_data.get('overall_duration_months', 0)} months")
    lines.append(f"**Total Estimated Cost:** ${roadmap_data.get('total_estimated_cost_usd', 0):,}")
    lines.append(f"**Migration Strategy:** {roadmap_data.get('migration_strategy', 'N/A')}")
    lines.append("")

    phases = roadmap_data.get('phases', [])
    if phases:
        lines.append("### Implementation Phases")
        lines.append("")
        for phase in phases:
            lines.append(f"#### Phase {phase.get('phase')}: {phase.get('name')}")
            lines.append(f"- **Duration:** {phase.get('duration_months')} months (Months {phase.get('start_month')}-{phase.get('end_month')})")
            lines.append(f"- **Estimated Cost:** ${phase.get('cost_usd', 0):,}")
            lines.append("")

            components = phase.get('components', [])
            if components:
                lines.append("**Components:**")
                for comp in components:
                    lines.append(f"- {comp.get('component')} ({comp.get('modernization_approach')})")
                    lines.append(f"  - Effort: {comp.get('estimated_effort_weeks')} weeks")
                    lines.append(f"  - Cost: ${comp.get('estimated_cost_usd', 0):,}")
                lines.append("")

            deliverables = phase.get('deliverables', [])
            if deliverables:
                lines.append("**Key Deliverables:**")
                for deliv in deliverables:
                    lines.append(f"- {deliv}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Success Factors
    success_factors = roadmap_data.get('success_factors', [])
    if success_factors:
        lines.append("## Critical Success Factors")
        lines.append("")
        for factor in success_factors:
            lines.append(f"- {factor}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Key Risks
    key_risks = roadmap_data.get('key_risks', [])
    if key_risks:
        lines.append("## Key Risks & Mitigation")
        lines.append("")
        for risk in key_risks:
            lines.append(f"### {risk.get('category')} Risk")
            lines.append(f"**Description:** {risk.get('description')}")
            lines.append(f"**Mitigation:** {risk.get('mitigation')}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by Cobalt ETL Studio - Discovery V2 on {bp_data.get('generated_at', 'N/A')}*")

    return "\n".join(lines)


def read_summary(artifacts_prefix: str) -> Dict[str, Any]:
    """Read and build summary from all artifacts"""

    summary = {}

    # Read AI analysis for file count
    ai_data = read_json_file(f"{artifacts_prefix}ai_discovery_analysis.json")
    summary['total_files_analyzed'] = ai_data.get('summary', {}).get('total_files_analyzed', 0)

    # Read business processes
    bp_data = read_json_file(f"{artifacts_prefix}business_processes.json")
    summary['business_processes_discovered'] = bp_data.get('summary', {}).get('total_processes', 0)
    summary['high_value_processes'] = bp_data.get('summary', {}).get('high_value_processes', 0)

    # Read integration points
    int_data = read_json_file(f"{artifacts_prefix}integration_points.json")
    summary['integration_points_discovered'] = int_data.get('summary', {}).get('total_integration_points', 0)
    summary['high_complexity_integrations'] = int_data.get('summary', {}).get('high_complexity_count', 0)

    # Read API pattern
    api_data = read_json_file(f"{artifacts_prefix}api_patterns.json")
    summary['api_pattern_detected'] = api_data.get('primary_api_pattern', 'unknown')

    # Read ROI
    roi_data = read_json_file(f"{artifacts_prefix}roi_analysis.json")
    summary['total_savings_5_years'] = roi_data.get('summary', {}).get('total_savings_5_years', 0)
    summary['roi_percent'] = roi_data.get('summary', {}).get('roi_percent', 0)
    summary['payback_period_months'] = roi_data.get('summary', {}).get('payback_period_months', 0)

    # Read roadmap
    roadmap_data = read_json_file(f"{artifacts_prefix}migration_roadmap.json")
    summary['migration_duration_months'] = roadmap_data.get('overall_duration_months', 0)
    summary['total_migration_cost'] = roadmap_data.get('total_estimated_cost_usd', 0)

    return summary


def read_json_file(s3_key: str) -> Dict[str, Any]:
    """Read JSON file from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read())
    except s3_client.exceptions.NoSuchKey:
        print(f"WARNING: File not found: {s3_key}")
        return {}
    except Exception as e:
        print(f"ERROR reading {s3_key}: {str(e)}")
        return {}


def extract_section(artifacts_prefix: str, section: str) -> Any:
    """
    Extract specific section from artifacts for UI-friendly return

    Supports nested paths like: ai_discovery_analysis.analysis_text
    """
    # Map section to file and path
    section_mapping = {
        'business_processes': (f"{artifacts_prefix}business_processes.json", None),
        'integration_points': (f"{artifacts_prefix}integration_points.json", None),
        'api_patterns': (f"{artifacts_prefix}api_patterns.json", None),
        'roi_analysis': (f"{artifacts_prefix}roi_analysis.json", None),
        'roadmap': (f"{artifacts_prefix}migration_roadmap.json", None),
        'discovery_report': (f"{artifacts_prefix}discovery_report.json", None),
        'ai_discovery_analysis': (f"{artifacts_prefix}ai_discovery_analysis.json", None),

        # Support nested paths (like V1 analysis_text)
        'ai_discovery_analysis.analysis_text': (f"{artifacts_prefix}ai_discovery_analysis.json", 'analysis_text'),
        'discovery_report.executive_summary': (f"{artifacts_prefix}discovery_report.json", 'executive_summary'),
    }

    # Check if section exists
    if section not in section_mapping:
        return f"Unknown section: {section}"

    file_path, nested_key = section_mapping[section]
    data = read_json_file(file_path)

    # If nested key specified, extract it
    if nested_key and isinstance(data, dict):
        return data.get(nested_key, f"Key '{nested_key}' not found")

    return data
