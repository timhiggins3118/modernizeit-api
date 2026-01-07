"""
Dependency Mapper V2 - Results API Handler
Lambda: DependencyMapperV2ResultsAPI

Purpose: Return dependency analysis results via API Gateway GET /resultsdmv2/{job_id}

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get Dependency Mapper Results

    Input (from API Gateway):
    {
        "pathParameters": {
            "job_id": "dmv2_job_5150_TestApp01_1759500000_abc123de"
        },
        "queryStringParameters": {
            "section": "dependency_graph"  # Optional: all, dependency_graph, coupling_metrics, risk_assessment, microservice_boundaries, impact_analysis
        }
    }

    Output:
    {
        "statusCode": 200,
        "body": "{\"job_id\": \"...\", \"section\": \"all\", \"data\": {...}}"
    }
    """
    try:
        # Parse job_id from path
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

        # Parse section from query parameters
        query_params = event.get('queryStringParameters') or {}
        section = query_params.get('section', 'all')

        print(f"Getting results for job {job_id}, section: {section}")

        # Extract account and app from job_id
        parts = job_id.split('_')
        if len(parts) < 5 or parts[0] != 'dmv2' or parts[1] != 'job':
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid job_id format',
                    'expected_format': 'dmv2_job_{account}_{app}_{timestamp}_{uuid}'
                })
            }

        scout_account_id = parts[2]
        application_name = parts[3]

        # Check if job is completed
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"

        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Job not found',
                    'job_id': job_id
                })
            }

        # Check if completed
        if status_data.get('state') != 'completed':
            return {
                'statusCode': 202,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'message': 'Job not yet completed',
                    'status': status_data.get('state'),
                    'progress': status_data.get('progress', 0),
                    'check_status_url': f'/statusdmv2/{job_id}'
                })
            }

        # Build results based on section requested
        artifacts_path = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts"

        # Special handling for analysis_text - generate comprehensive markdown report
        if section == 'analysis_text':
            markdown_report = generate_analysis_report(artifacts_path, job_id)

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'data': markdown_report
                }, indent=2)
            }

        if section == 'all':
            # Return all artifacts
            data = {
                'summary': get_summary(artifacts_path),
                'dependency_graph': read_artifact(f"{artifacts_path}/dependency_graph.json"),
                'coupling_metrics': read_artifact(f"{artifacts_path}/coupling_metrics.json"),
                'risk_assessment': read_artifact(f"{artifacts_path}/risk_assessment.json"),
                'microservice_boundaries': read_artifact(f"{artifacts_path}/microservice_boundaries.json"),
                'impact_analysis': read_artifact(f"{artifacts_path}/impact_analysis.json")
            }

        elif section == 'dependency_graph':
            data = read_artifact(f"{artifacts_path}/dependency_graph.json")

        elif section == 'coupling_metrics':
            data = read_artifact(f"{artifacts_path}/coupling_metrics.json")

        elif section == 'risk_assessment':
            data = read_artifact(f"{artifacts_path}/risk_assessment.json")

        elif section == 'microservice_boundaries':
            data = read_artifact(f"{artifacts_path}/microservice_boundaries.json")

        elif section == 'impact_analysis':
            data = read_artifact(f"{artifacts_path}/impact_analysis.json")

        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid section',
                    'valid_sections': ['all', 'dependency_graph', 'coupling_metrics', 'risk_assessment', 'microservice_boundaries', 'impact_analysis']
                })
            }

        # Build response
        response_body = {
            'job_id': job_id,
            'section': section,
            'data': data
        }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body, indent=2)
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2ResultsAPI: {str(e)}")
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


def generate_analysis_report(artifacts_path: str, job_id: str) -> str:
    """
    Generate comprehensive dependency analysis report in markdown format
    Combines all V2 artifacts into a readable report
    """
    lines = []

    # Read all artifacts
    summary_data = get_summary(artifacts_path)
    graph_data = read_artifact(f"{artifacts_path}/dependency_graph.json")
    coupling_data = read_artifact(f"{artifacts_path}/coupling_metrics.json")
    risk_data = read_artifact(f"{artifacts_path}/risk_assessment.json")
    ms_data = read_artifact(f"{artifacts_path}/microservice_boundaries.json")
    impact_data = read_artifact(f"{artifacts_path}/impact_analysis.json")
    static_data = read_artifact(f"{artifacts_path}/static_analysis.json")

    # Header
    lines.append("# COBOL Dependency Analysis Report")
    lines.append("")
    lines.append(f"**Job ID:** {job_id}")
    lines.append(f"**Generated:** {graph_data.get('generated_at', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Total Programs Analyzed:** {summary_data.get('total_programs_analyzed', 0)}")
    lines.append(f"- **Total Dependencies Found:** {summary_data.get('total_dependencies', 0)}")
    lines.append(f"- **Program Calls:** {summary_data.get('program_calls', 0)}")
    lines.append(f"- **Copybook Dependencies:** {summary_data.get('copybook_dependencies', 0)}")
    lines.append(f"- **File Operations:** {summary_data.get('file_operations', 0)}")
    lines.append(f"- **Database Operations:** {summary_data.get('database_operations', 0)}")
    lines.append("")
    lines.append(f"- **Graph Nodes:** {summary_data.get('graph_nodes', 0)}")
    lines.append(f"- **Graph Edges:** {summary_data.get('graph_edges', 0)}")
    lines.append(f"- **Circular Dependencies:** {summary_data.get('circular_dependencies_count', 0)}")
    lines.append("")
    lines.append(f"- **High Coupling Programs:** {summary_data.get('high_coupling_programs', 0)}")
    lines.append(f"- **Average Coupling Factor:** {summary_data.get('average_coupling', 0):.3f}")
    lines.append("")
    lines.append(f"- **High Risk Areas:** {summary_data.get('high_risk_areas', 0)}")
    lines.append(f"- **Medium Risk Areas:** {summary_data.get('medium_risk_areas', 0)}")
    lines.append("")
    lines.append(f"- **Microservice Boundaries Suggested:** {summary_data.get('microservice_boundaries_suggested', 0)}")
    lines.append(f"- **Average Impact Radius:** {summary_data.get('average_impact_radius', 0):.2f}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Dependency Graph
    lines.append("## Dependency Graph")
    lines.append("")
    graph_summary = graph_data.get('summary', {})
    lines.append(f"- **Total Nodes:** {graph_summary.get('total_nodes', 0)}")
    lines.append(f"- **Total Edges:** {graph_summary.get('total_edges', 0)}")
    lines.append(f"- **Max Depth:** {graph_summary.get('max_depth', 0)}")
    lines.append(f"- **Cyclic Groups:** {graph_summary.get('cyclic_groups', 0)}")
    lines.append("")

    edges = graph_data.get('edges', [])
    if edges:
        lines.append("### Program Call Relationships")
        lines.append("")
        for edge in edges[:10]:  # Limit to first 10 to keep report manageable
            lines.append(f"- `{edge.get('from')}` → `{edge.get('to')}` (Line {edge.get('line_number', 'N/A')})")
        if len(edges) > 10:
            lines.append(f"- ... and {len(edges) - 10} more relationships")
        lines.append("")
    else:
        lines.append("No program call relationships detected.")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Coupling Metrics
    lines.append("## Coupling Metrics")
    lines.append("")
    coupling_overall = coupling_data.get('overall', {})
    lines.append(f"- **Average Fan-In:** {coupling_overall.get('average_fan_in', 0):.2f}")
    lines.append(f"- **Average Fan-Out:** {coupling_overall.get('average_fan_out', 0):.2f}")
    lines.append(f"- **Average Coupling:** {coupling_overall.get('average_coupling', 0):.3f}")
    lines.append(f"- **High Coupling Count:** {coupling_overall.get('high_coupling_count', 0)}")
    lines.append(f"- **Medium Coupling Count:** {coupling_overall.get('medium_coupling_count', 0)}")
    lines.append(f"- **Low Coupling Count:** {coupling_overall.get('low_coupling_count', 0)}")
    lines.append("")

    # Show top coupled programs
    by_program = coupling_data.get('by_program', [])
    high_coupled = [p for p in by_program if p.get('classification') == 'High Coupling']
    if high_coupled:
        lines.append("### High Coupling Programs")
        lines.append("")
        for prog in high_coupled[:5]:
            lines.append(f"- **{prog.get('program')}**")
            lines.append(f"  - Fan-In: {prog.get('fan_in', 0)}, Fan-Out: {prog.get('fan_out', 0)}")
            lines.append(f"  - Coupling Factor: {prog.get('coupling_factor', 0):.3f}")
            lines.append(f"  - Cohesion Score: {prog.get('cohesion_score', 0):.2f}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Risk Assessment
    lines.append("## Risk Assessment")
    lines.append("")
    risk_summary = risk_data.get('summary', {})
    lines.append(f"- **High Risk Items:** {risk_summary.get('high_risk_count', 0)}")
    lines.append(f"- **Medium Risk Items:** {risk_summary.get('medium_risk_count', 0)}")
    lines.append(f"- **Total Risk Items:** {risk_summary.get('total_risk_items', 0)}")
    lines.append("")

    # Circular dependencies
    circular_deps = risk_data.get('circular_dependencies', [])
    if circular_deps:
        lines.append("### Circular Dependencies")
        lines.append("")
        for circ in circular_deps:
            cycle = circ.get('cycle', [])
            lines.append(f"- **{' → '.join(cycle)}** (Risk: {circ.get('risk_level', 'N/A')})")
        lines.append("")

    # Tight coupling areas
    tight_coupling = risk_data.get('tight_coupling_areas', [])
    if tight_coupling:
        lines.append("### Tight Coupling Areas")
        lines.append("")
        for area in tight_coupling[:5]:
            lines.append(f"- **{area.get('program')}**")
            lines.append(f"  - Coupling: {area.get('coupling_factor', 0):.3f}, Risk: {area.get('risk_level', 'N/A')}")
        lines.append("")

    # Single points of failure
    spof = risk_data.get('single_points_of_failure', [])
    if spof:
        lines.append("### Single Points of Failure")
        lines.append("")
        for point in spof:
            lines.append(f"- **{point.get('program')}** (Dependents: {point.get('dependent_count', 0)})")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Microservice Boundaries
    lines.append("## Microservice Boundary Recommendations")
    lines.append("")
    ms_summary = ms_data.get('summary', {})
    lines.append(f"- **Suggested Services:** {ms_summary.get('total_services_suggested', 0)}")
    lines.append(f"- **Shared Components:** {ms_summary.get('total_shared_components', 0)}")
    lines.append("")

    suggested_services = ms_data.get('suggested_services', [])
    if suggested_services:
        lines.append("### Top Service Boundaries")
        lines.append("")
        for service in suggested_services[:5]:
            lines.append(f"#### {service.get('service_name')}")
            lines.append(f"- **Programs:** {service.get('program_count', 0)}")
            lines.append(f"- **Internal Coupling:** {service.get('internal_coupling', 0):.2f}")
            lines.append(f"- **External Coupling:** {service.get('external_coupling', 0):.2f}")
            lines.append(f"- **Cohesion Score:** {service.get('cohesion_score', 0):.2f}")
            lines.append(f"- **Justification:** {service.get('justification', 'N/A')}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # Impact Analysis
    lines.append("## Impact Analysis")
    lines.append("")
    impact_summary = impact_data.get('summary', {})
    lines.append(f"- **Total Programs:** {impact_summary.get('total_programs', 0)}")
    lines.append(f"- **High Impact Programs:** {impact_summary.get('high_impact_programs', 0)}")
    lines.append(f"- **Medium-High Impact Programs:** {impact_summary.get('medium_high_impact_programs', 0)}")
    lines.append(f"- **Average Impact Radius:** {impact_summary.get('average_impact_radius', 0):.2f}")
    lines.append("")

    sorted_impact = impact_data.get('sorted_by_impact', [])
    high_impact = [p for p in sorted_impact if p.get('risk_level') in ['High', 'Medium-High']]
    if high_impact:
        lines.append("### High Impact Programs")
        lines.append("")
        for prog in high_impact[:5]:
            lines.append(f"#### {prog.get('program')}")
            lines.append(f"- **Direct Dependents:** {prog.get('direct_dependents_count', 0)}")
            lines.append(f"- **Indirect Dependents:** {prog.get('indirect_dependents_count', 0)}")
            lines.append(f"- **Total Impact Radius:** {prog.get('total_impact_radius', 0)}")
            lines.append(f"- **Risk Level:** {prog.get('risk_level', 'N/A')}")
            lines.append(f"- **Recommendation:** {prog.get('refactoring_recommendation', 'N/A')}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # Per-Program Static Analysis Summary
    if static_data and 'files' in static_data:
        files = static_data.get('files', [])
        if files:
            lines.append("## Detailed Program Dependencies")
            lines.append("")
            for file_data in files[:3]:  # Show first 3 programs
                program_id = file_data.get('program_id', 'Unknown')
                lines.append(f"### {program_id}")
                lines.append("")

                # Copybooks
                copybooks = file_data.get('dependencies', {}).get('copybooks', [])
                if copybooks:
                    lines.append("**Copybooks:**")
                    for cb in copybooks:
                        lines.append(f"- {cb.get('name', 'N/A')} (Line {cb.get('line_number', 'N/A')})")
                    lines.append("")

                # Files
                files_deps = file_data.get('dependencies', {}).get('files', [])
                if files_deps:
                    lines.append("**Files:**")
                    for f in files_deps:
                        lines.append(f"- {f.get('name', 'N/A')} ({f.get('type', 'N/A')}, Line {f.get('line_number', 'N/A')})")
                    lines.append("")

                # Database
                db_deps = file_data.get('dependencies', {}).get('database', [])
                if db_deps:
                    lines.append("**Database:**")
                    for db in db_deps:
                        lines.append(f"- {db.get('name', 'N/A')} ({db.get('type', 'N/A')}, Line {db.get('line_number', 'N/A')})")
                    lines.append("")

                # Program calls
                prog_calls = file_data.get('dependencies', {}).get('program_calls', [])
                if prog_calls:
                    lines.append("**Program Calls:**")
                    for pc in prog_calls:
                        lines.append(f"- {pc.get('name', 'N/A')} (Line {pc.get('line_number', 'N/A')})")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # Footer
    lines.append("*Generated by Cobalt ETL Studio - Dependency Mapper V2*")

    return "\n".join(lines)


def read_artifact(artifact_key: str) -> Dict[str, Any]:
    """Read artifact from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=artifact_key)
        return json.loads(response['Body'].read())
    except s3_client.exceptions.NoSuchKey:
        return {'error': 'Artifact not found', 'key': artifact_key}
    except Exception as e:
        return {'error': str(e)}


def get_summary(artifacts_path: str) -> Dict[str, Any]:
    """Build summary from all artifacts"""
    try:
        # Read dependency_graph
        graph_data = read_artifact(f"{artifacts_path}/dependency_graph.json")
        graph_summary = graph_data.get('summary', {})

        # Read static_analysis
        static_data = read_artifact(f"{artifacts_path}/static_analysis.json")
        static_summary = static_data.get('summary', {})

        # Read coupling_metrics
        coupling_data = read_artifact(f"{artifacts_path}/coupling_metrics.json")
        coupling_overall = coupling_data.get('overall', {})

        # Read risk_assessment
        risk_data = read_artifact(f"{artifacts_path}/risk_assessment.json")
        risk_summary = risk_data.get('summary', {})

        # Read microservice_boundaries
        ms_data = read_artifact(f"{artifacts_path}/microservice_boundaries.json")
        ms_summary = ms_data.get('summary', {})

        # Read impact_analysis
        impact_data = read_artifact(f"{artifacts_path}/impact_analysis.json")
        impact_summary = impact_data.get('summary', {})

        return {
            'total_programs_analyzed': static_summary.get('total_programs', 0),
            'total_dependencies': static_summary.get('total_dependencies', 0),
            'program_calls': static_summary.get('program_calls', 0),
            'copybook_dependencies': static_summary.get('copybook_dependencies', 0),
            'file_operations': static_summary.get('file_operations', 0),
            'database_operations': static_summary.get('database_operations', 0),
            'graph_nodes': graph_summary.get('total_nodes', 0),
            'graph_edges': graph_summary.get('total_edges', 0),
            'circular_dependencies_count': graph_summary.get('cyclic_groups', 0),
            'high_coupling_programs': coupling_overall.get('high_coupling_count', 0),
            'average_coupling': coupling_overall.get('average_coupling', 0),
            'high_risk_areas': risk_summary.get('high_risk_count', 0),
            'medium_risk_areas': risk_summary.get('medium_risk_count', 0),
            'microservice_boundaries_suggested': ms_summary.get('total_services_suggested', 0),
            'shared_components': ms_summary.get('total_shared_components', 0),
            'high_impact_programs': impact_summary.get('high_impact_programs', 0),
            'average_impact_radius': impact_summary.get('average_impact_radius', 0)
        }

    except Exception as e:
        print(f"Failed to build summary: {str(e)}")
        return {'error': 'Failed to build summary', 'message': str(e)}
