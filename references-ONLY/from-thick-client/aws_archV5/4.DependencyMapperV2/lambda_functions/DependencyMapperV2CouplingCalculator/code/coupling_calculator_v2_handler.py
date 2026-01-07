"""
Dependency Mapper V2 - Coupling Calculator Handler
Lambda: DependencyMapperV2CouplingCalculator

Purpose: Calculate coupling/cohesion metrics for programs

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
- Runs in parallel with RiskAssessor
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Calculate Coupling Metrics

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "coupling_metrics_calculated": true,
        "high_coupling_count": 5
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Calculating coupling metrics for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'calculating_coupling', 70, 'Calculating coupling metrics')

        # Read dependency_graph.json
        graph_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"
        graph_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=graph_key)
        graph_data = json.loads(graph_response['Body'].read())

        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])

        # Calculate coupling metrics for each program
        program_metrics = []
        high_coupling_count = 0
        medium_coupling_count = 0
        low_coupling_count = 0

        total_fan_in = 0
        total_fan_out = 0
        total_coupling = 0
        program_count = 0

        for node in nodes:
            if node['type'] == 'program':
                program = node['id']
                fan_in = node.get('fan_in', 0)
                fan_out = node.get('fan_out', 0)

                # Calculate coupling factor: (fan_in + fan_out) / (total_programs - 1)
                # Range: 0.0 (no coupling) to 1.0 (fully coupled)
                coupling_factor = (fan_in + fan_out) / max(len(nodes) - 1, 1)

                # Calculate cohesion score (simplified heuristic)
                # High cohesion = low fan-out (focused responsibility)
                cohesion_score = 1.0 - min(fan_out / 10.0, 1.0)

                # Classify coupling
                if coupling_factor > 0.7:
                    classification = "High Coupling"
                    high_coupling_count += 1
                elif coupling_factor > 0.4:
                    classification = "Medium Coupling"
                    medium_coupling_count += 1
                else:
                    classification = "Low Coupling"
                    low_coupling_count += 1

                program_metrics.append({
                    'program': program,
                    'fan_in': fan_in,
                    'fan_out': fan_out,
                    'coupling_factor': round(coupling_factor, 3),
                    'cohesion_score': round(cohesion_score, 3),
                    'classification': classification
                })

                total_fan_in += fan_in
                total_fan_out += fan_out
                total_coupling += coupling_factor
                program_count += 1

        # Calculate overall metrics
        avg_fan_in = round(total_fan_in / program_count, 2) if program_count > 0 else 0
        avg_fan_out = round(total_fan_out / program_count, 2) if program_count > 0 else 0
        avg_coupling = round(total_coupling / program_count, 3) if program_count > 0 else 0

        # Sort by coupling factor (descending)
        program_metrics.sort(key=lambda x: x['coupling_factor'], reverse=True)

        coupling_metrics = {
            'by_program': program_metrics,
            'overall': {
                'total_programs': program_count,
                'average_fan_in': avg_fan_in,
                'average_fan_out': avg_fan_out,
                'average_coupling': avg_coupling,
                'high_coupling_count': high_coupling_count,
                'medium_coupling_count': medium_coupling_count,
                'low_coupling_count': low_coupling_count
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/coupling_metrics.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(coupling_metrics, indent=2),
            ContentType='application/json'
        )

        print(f"Saved coupling metrics to s3://{BUCKET_NAME}/{output_key}")
        print(f"Coupling: {high_coupling_count} high, {medium_coupling_count} medium, {low_coupling_count} low")

        # Update status
        update_status(status_key, 'running', 'coupling_calculated', 75, f'{high_coupling_count} high-coupling programs identified')

        return {
            'coupling_metrics_calculated': True,
            'high_coupling_count': high_coupling_count
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2CouplingCalculator: {str(e)}")
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
