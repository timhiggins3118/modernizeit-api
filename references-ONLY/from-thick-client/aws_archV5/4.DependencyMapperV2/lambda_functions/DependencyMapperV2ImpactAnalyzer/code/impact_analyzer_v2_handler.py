"""
Dependency Mapper V2 - Impact Analyzer Handler
Lambda: DependencyMapperV2ImpactAnalyzer

Purpose: Calculate impact radius for each program (blast radius for changes)

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List, Set

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Calculate Impact Analysis

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "impact_analysis_complete": true,
        "programs_analyzed": 23
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Calculating impact analysis for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'impact_analysis', 90, 'Calculating impact radius for programs')

        # Read dependency_graph.json
        graph_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"
        graph_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=graph_key)
        graph_data = json.loads(graph_response['Body'].read())

        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])

        # Build reverse adjacency list (who calls this program)
        callers = {}  # program -> list of programs that call it
        callees = {}  # program -> list of programs it calls

        for edge in edges:
            if edge['type'] in ['CALL', 'LINK', 'XCTL']:
                source = edge['from']
                target = edge['to']

                if target not in callers:
                    callers[target] = []
                callers[target].append(source)

                if source not in callees:
                    callees[source] = []
                callees[source].append(target)

        # Calculate impact for each program
        impact_analysis = {}

        for node in nodes:
            if node['type'] == 'program':
                program = node['id']

                # Direct dependents (programs that call this one)
                direct_dependents = callers.get(program, [])

                # Indirect dependents (transitive - programs that call the direct dependents)
                indirect_dependents = set()
                visited = set()

                def find_transitive_callers(prog: str, depth: int = 0):
                    if depth > 5 or prog in visited:  # Limit depth to avoid infinite loops
                        return
                    visited.add(prog)

                    for caller in callers.get(prog, []):
                        if caller != program and caller not in direct_dependents:
                            indirect_dependents.add(caller)
                            find_transitive_callers(caller, depth + 1)

                for dep in direct_dependents:
                    find_transitive_callers(dep)

                total_impact_radius = len(direct_dependents) + len(indirect_dependents)

                # Determine risk level
                if total_impact_radius == 0:
                    risk_level = 'Low'
                    refactoring_rec = 'Low impact - safe to refactor independently'
                elif total_impact_radius <= 3:
                    risk_level = 'Low-Medium'
                    refactoring_rec = 'Limited impact - minimal coordination needed'
                elif total_impact_radius <= 8:
                    risk_level = 'Medium'
                    refactoring_rec = 'Moderate impact - requires coordination with dependent teams'
                elif total_impact_radius <= 15:
                    risk_level = 'Medium-High'
                    refactoring_rec = 'Significant impact - requires phased approach with extensive testing'
                else:
                    risk_level = 'High'
                    refactoring_rec = 'Major impact - requires careful planning, staged rollout, and comprehensive testing'

                impact_analysis[program] = {
                    'program': program,
                    'direct_dependents': direct_dependents,
                    'direct_dependents_count': len(direct_dependents),
                    'indirect_dependents': list(indirect_dependents),
                    'indirect_dependents_count': len(indirect_dependents),
                    'total_impact_radius': total_impact_radius,
                    'risk_level': risk_level,
                    'refactoring_recommendation': refactoring_rec,
                    'programs_it_calls': callees.get(program, []),
                    'programs_it_calls_count': len(callees.get(program, []))
                }

        # Sort by impact radius (descending)
        sorted_impact = sorted(
            impact_analysis.values(),
            key=lambda x: x['total_impact_radius'],
            reverse=True
        )

        # Calculate summary
        high_impact_count = sum(1 for ia in sorted_impact if ia['risk_level'] == 'High')
        medium_high_impact_count = sum(1 for ia in sorted_impact if ia['risk_level'] == 'Medium-High')
        medium_impact_count = sum(1 for ia in sorted_impact if ia['risk_level'] == 'Medium')

        impact_data = {
            'program_impact_map': {ia['program']: ia for ia in sorted_impact},
            'sorted_by_impact': sorted_impact,
            'summary': {
                'total_programs': len(sorted_impact),
                'high_impact_programs': high_impact_count,
                'medium_high_impact_programs': medium_high_impact_count,
                'medium_impact_programs': medium_impact_count,
                'average_impact_radius': round(sum(ia['total_impact_radius'] for ia in sorted_impact) / len(sorted_impact), 2) if sorted_impact else 0
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/impact_analysis.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(impact_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved impact analysis to s3://{BUCKET_NAME}/{output_key}")
        print(f"Impact: {high_impact_count} high-impact programs")

        # Update status
        update_status(status_key, 'running', 'impact_analysis_complete', 95, f'Impact analysis complete: {high_impact_count} high-impact programs')

        return {
            'impact_analysis_complete': True,
            'programs_analyzed': len(sorted_impact)
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2ImpactAnalyzer: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def update_status(status_key: str, status: str, phase: str, progress: int, message: str):
    """Update job status in S3"""
    try:
        # Read current status
        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            status_data = {}

        # Update fields
        status_data['state'] = status
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Write back
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {status} - {phase} ({progress}%) - {message}")

    except Exception as e:
        print(f"Failed to update status: {str(e)}")
