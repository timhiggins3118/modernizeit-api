"""
Dependency Mapper V2 - Risk Assessor Handler
Lambda: DependencyMapperV2RiskAssessor

Purpose: Assess architectural risks from dependencies

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
- Runs in parallel with CouplingCalculator
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Assess Architectural Risks

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "risk_assessment_complete": true,
        "high_risk_count": 3
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Assessing risks for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'assessing_risks', 70, 'Assessing architectural risks')

        # Read dependency_graph.json
        graph_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"
        graph_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=graph_key)
        graph_data = json.loads(graph_response['Body'].read())

        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        summary = graph_data.get('summary', {})
        cycles = summary.get('cycles', [])

        # Risk 1: Circular Dependencies
        circular_deps = []
        for cycle in cycles:
            circular_deps.append({
                'cycle': cycle,
                'risk_level': 'High',
                'recommendation': 'Break circular dependency by introducing interface or removing bidirectional call'
            })

        # Risk 2: Tight Coupling (high fan-in AND high fan-out)
        tight_coupling = []
        for node in nodes:
            if node['type'] == 'program':
                fan_in = node.get('fan_in', 0)
                fan_out = node.get('fan_out', 0)

                if fan_in >= 5 and fan_out >= 5:
                    # Find what this program is coupled with
                    coupled_with = [
                        edge['to'] for edge in edges
                        if edge['from'] == node['id'] and edge['type'] in ['CALL', 'LINK', 'XCTL']
                    ]

                    coupling_score = (fan_in + fan_out) / max(len(nodes) - 1, 1)

                    tight_coupling.append({
                        'program': node['id'],
                        'fan_in': fan_in,
                        'fan_out': fan_out,
                        'coupled_with': coupled_with[:5],  # Top 5
                        'coupling_score': round(coupling_score, 3),
                        'risk_level': 'High',
                        'recommendation': 'Refactor to reduce coupling; consider extracting common functionality'
                    })

        # Risk 3: Single Points of Failure (very high fan-in)
        single_points = []
        for node in nodes:
            if node['type'] == 'program':
                fan_in = node.get('fan_in', 0)

                if fan_in >= 10:
                    single_points.append({
                        'program': node['id'],
                        'fan_in': fan_in,
                        'risk': f'{fan_in} programs depend on this - single point of failure',
                        'risk_level': 'High',
                        'recommendation': 'Ensure comprehensive testing and monitoring; consider redundancy'
                    })

        # Risk 4: God Programs (very high fan-out)
        god_programs = []
        for node in nodes:
            if node['type'] == 'program':
                fan_out = node.get('fan_out', 0)

                if fan_out >= 10:
                    god_programs.append({
                        'program': node['id'],
                        'fan_out': fan_out,
                        'risk': f'Calls {fan_out} other programs - too many responsibilities',
                        'risk_level': 'Medium-High',
                        'recommendation': 'Refactor to split responsibilities into smaller, focused programs'
                    })

        # Risk 5: Shared Copybooks (high usage)
        shared_copybooks = []
        for node in nodes:
            if node['type'] == 'copybook':
                used_by_count = node.get('used_by_count', 0)

                if used_by_count >= 8:
                    shared_copybooks.append({
                        'copybook': node['id'],
                        'used_by_count': used_by_count,
                        'risk': f'Used by {used_by_count} programs - changes have wide impact',
                        'risk_level': 'Medium',
                        'recommendation': 'Version carefully; consider breaking into smaller, focused copybooks'
                    })

        # Calculate risk summary
        high_risk_count = len(circular_deps) + len(tight_coupling) + len(single_points)
        medium_risk_count = len(god_programs) + len(shared_copybooks)

        risk_assessment = {
            'circular_dependencies': circular_deps,
            'tight_coupling_areas': tight_coupling,
            'single_points_of_failure': single_points,
            'god_programs': god_programs,
            'shared_copybooks': shared_copybooks,
            'summary': {
                'high_risk_count': high_risk_count,
                'medium_risk_count': medium_risk_count,
                'total_risk_items': high_risk_count + medium_risk_count
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/risk_assessment.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(risk_assessment, indent=2),
            ContentType='application/json'
        )

        print(f"Saved risk assessment to s3://{BUCKET_NAME}/{output_key}")
        print(f"Risks: {high_risk_count} high, {medium_risk_count} medium")

        # Update status
        update_status(status_key, 'running', 'risks_assessed', 75, f'Identified {high_risk_count} high-risk areas')

        return {
            'risk_assessment_complete': True,
            'high_risk_count': high_risk_count
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2RiskAssessor: {str(e)}")
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
