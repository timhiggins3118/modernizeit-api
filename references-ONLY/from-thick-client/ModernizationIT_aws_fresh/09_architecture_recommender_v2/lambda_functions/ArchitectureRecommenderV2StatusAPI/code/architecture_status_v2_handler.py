"""
Architecture Recommender V2 - Status API Handler
Lambda: ArchitectureRecommenderV2StatusAPI

Purpose: API handler for checking job status

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
    Status API Handler

    Input (from API Gateway):
    {
        "pathParameters": {
            "job_id": "ar2_job_5150_TestApp01_1759520000_abc123de"
        }
    }

    Output:
    {
        "statusCode": 200,
        "body": "{...}"
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - STATUS API")
        print("=" * 80)

        # Get job_id from path parameters
        path_params = event.get('pathParameters', {})
        job_id = path_params.get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id in path')

        print(f"Job ID: {job_id}")

        # Parse job_id to extract account and app
        # Format: ar2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')
        if len(parts) < 6 or not job_id.startswith('ar2_job_'):
            return error_response(400, 'Invalid job_id format. Expected: ar2_job_{account}_{app}_{timestamp}_{uuid}')

        scout_account_id = parts[2]
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        print(f"Account: {scout_account_id}, App: {application_name}")

        # Read status.json
        status_key = f"{scout_account_id}/{application_name}/architecture_v2/jobs/{job_id}/status.json"

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_content = response['Body'].read().decode('utf-8')
            status_data = json.loads(status_content)

            # Handle double-encoded JSON (if status is a string, parse again)
            if isinstance(status_data, str):
                status_data = json.loads(status_data)

        except s3_client.exceptions.NoSuchKey:
            return error_response(404, f'Job not found: {job_id}')

        # Check if results exist
        has_results = check_results_exist(scout_account_id, application_name, job_id)

        # Build response
        job_state = status_data.get('state', status_data.get('status', 'unknown'))
        job_status = 'completed' if job_state == 'completed' else 'running' if job_state in ['running', 'pending'] else 'failed'

        response_body = {
            'job_id': job_id,
            'status': job_status,
            'progress': status_data.get('progress', 0),
            'phase': status_data.get('phase', 'unknown'),
            'started_at': status_data.get('started_at'),
            'completed_at': status_data.get('completed_at'),
            'message': status_data.get('message', ''),
            'has_results': has_results,
            'results_url': f"/resultsar2/{job_id}" if has_results else None
        }

        # If completed, add summary
        if has_results:
            summary = generate_summary(scout_account_id, application_name, job_id)
            if summary:
                response_body['summary'] = summary

        print(f"Status: {job_status}, Progress: {response_body['progress']}%")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body, indent=2)
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return error_response(500, f'Internal server error: {str(e)}')


def check_results_exist(account_id: str, app_name: str, job_id: str) -> bool:
    """Check if final recommendations exist"""
    recommendations_key = f"{account_id}/{app_name}/architecture_v2/jobs/{job_id}/artifacts/architecture_recommendations.json"

    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=recommendations_key)
        return True
    except:
        return False


def generate_summary(account_id: str, app_name: str, job_id: str) -> Dict[str, Any]:
    """Generate summary from recommendations"""
    try:
        recommendations_key = f"{account_id}/{app_name}/architecture_v2/jobs/{job_id}/artifacts/architecture_recommendations.json"

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=recommendations_key)
        recommendations = json.loads(response['Body'].read().decode('utf-8'))

        summary = recommendations.get('summary', {})
        cost_breakdown = recommendations.get('cost_breakdown', {})

        return {
            'application_type': summary.get('application_type', 'unknown'),
            'recommended_architecture': summary.get('recommended_architecture', 'unknown'),
            'services_recommended': len(recommendations.get('service_mappings', [])),
            'estimated_monthly_cost_usd': cost_breakdown.get('total_monthly_usd', 0),
            'migration_duration_weeks': sum(
                phase.get('duration_weeks', 0)
                for phase in recommendations.get('migration_phases', [])
            ),
            'confidence': summary.get('confidence', 0)
        }

    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return None


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Build error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
