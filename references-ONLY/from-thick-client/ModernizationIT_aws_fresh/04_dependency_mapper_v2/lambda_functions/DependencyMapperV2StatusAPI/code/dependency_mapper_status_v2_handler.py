"""
Dependency Mapper V2 - Status API Handler
Lambda: DependencyMapperV2StatusAPI

Purpose: Return job status via API Gateway GET /statusdmv2/{job_id}

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
    Get Dependency Mapper Job Status

    Input (from API Gateway):
    {
        "pathParameters": {
            "job_id": "dmv2_job_5150_TestApp01_1759500000_abc123de"
        }
    }

    Output:
    {
        "statusCode": 200,
        "body": "{\"job_id\": \"...\", \"status\": \"completed\", ...}"
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

        print(f"Getting status for job {job_id}")

        # Extract account and app from job_id
        # Format: dmv2_job_{account}_{app}_{timestamp}_{uuid}
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

        # Read status.json from S3
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

        # Check if job is completed
        job_state = status_data.get('state', 'unknown')
        if job_state == 'completed':
            # Check if results exist
            has_results = check_results_exist(scout_account_id, application_name, job_id)

            # Get summary if available
            summary = get_summary(scout_account_id, application_name, job_id) if has_results else {}

            response_body = {
                'job_id': job_id,
                'status': job_state,
                'progress': status_data.get('progress', 100),
                'phase': status_data.get('phase', 'completed'),
                'started_at': status_data.get('created_at') or status_data.get('started_at'),
                'completed_at': status_data.get('last_updated'),
                'message': status_data.get('message', 'Dependency analysis completed'),
                'has_results': has_results,
                'results_url': f'/resultsdmv2/{job_id}' if has_results else None,
                'summary': summary
            }
        else:
            # Job still running or pending
            response_body = {
                'job_id': job_id,
                'status': job_state,
                'progress': status_data.get('progress', 0),
                'phase': status_data.get('phase', 'unknown'),
                'started_at': status_data.get('created_at') or status_data.get('started_at'),
                'message': status_data.get('message', 'Processing...'),
                'check_again_in_seconds': 30
            }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body, indent=2)
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2StatusAPI: {str(e)}")
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


def check_results_exist(scout_account_id: str, application_name: str, job_id: str) -> bool:
    """Check if dependency analysis results exist"""
    try:
        # Check for dependency_graph.json (primary artifact)
        graph_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"
        s3_client.head_object(Bucket=BUCKET_NAME, Key=graph_key)
        return True
    except:
        return False


def get_summary(scout_account_id: str, application_name: str, job_id: str) -> Dict[str, Any]:
    """Get summary of dependency analysis results"""
    try:
        # Read dependency_graph.json for summary
        graph_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"
        graph_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=graph_key)
        graph_data = json.loads(graph_response['Body'].read())

        graph_summary = graph_data.get('summary', {})

        # Read coupling_metrics.json
        coupling_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/coupling_metrics.json"
        coupling_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=coupling_key)
        coupling_data = json.loads(coupling_response['Body'].read())

        coupling_overall = coupling_data.get('overall', {})

        # Read risk_assessment.json
        risk_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/risk_assessment.json"
        risk_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=risk_key)
        risk_data = json.loads(risk_response['Body'].read())

        risk_summary = risk_data.get('summary', {})

        # Read microservice_boundaries.json
        ms_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/microservice_boundaries.json"
        ms_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ms_key)
        ms_data = json.loads(ms_response['Body'].read())

        ms_summary = ms_data.get('summary', {})

        return {
            'total_programs_analyzed': graph_summary.get('total_nodes', 0),
            'total_dependencies': graph_summary.get('total_edges', 0),
            'circular_dependencies': graph_summary.get('cyclic_groups', 0),
            'high_coupling_programs': coupling_overall.get('high_coupling_count', 0),
            'high_risk_areas': risk_summary.get('high_risk_count', 0),
            'suggested_microservices': ms_summary.get('total_services_suggested', 0)
        }

    except Exception as e:
        print(f"Failed to get summary: {str(e)}")
        return {}
