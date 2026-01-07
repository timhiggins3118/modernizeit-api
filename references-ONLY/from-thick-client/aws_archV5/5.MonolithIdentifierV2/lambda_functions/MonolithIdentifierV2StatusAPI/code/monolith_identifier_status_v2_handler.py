"""
Monolith Identifier V2 - Status API Handler
Lambda: MonolithIdentifierV2StatusAPI

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
            "job_id": "miv2_job_5150_TestApp01_1759500000_abc123de"
        }
    }

    Output:
    {
        "statusCode": 200,
        "body": "{\"job_id\": \"...\", \"status\": \"completed\", ...}"
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - STATUS API")
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

        print(f"Job ID: {job_id}")

        # Parse job_id to extract account and app
        # Format: miv2_job_{account}_{app}_{timestamp}_{uuid}
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

        # Read status.json
        status_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/status.json"

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_content = response['Body'].read().decode('utf-8')
            status_data = json.loads(status_content)

            # Handle double-encoded JSON (if status is a string, parse again)
            if isinstance(status_data, str):
                status_data = json.loads(status_data)
        except s3_client.exceptions.NoSuchKey:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Job not found',
                    'job_id': job_id
                })
            }

        # Check if artifacts exist (indicates completion)
        has_results = check_artifacts_exist(scout_account_id, application_name, job_id)

        # Build response
        job_state = status_data.get('state', status_data.get('status', 'unknown'))
        job_status = 'completed' if job_state == 'completed' else 'running' if job_state == 'running' else 'failed'

        response_body = {
            'job_id': job_id,
            'status': job_status,
            'progress': status_data.get('progress', 0),
            'phase': status_data.get('phase', 'unknown'),
            'started_at': status_data.get('started_at'),
            'completed_at': status_data.get('completed_at'),
            'message': status_data.get('message', ''),
            'has_results': has_results,
            'results_url': f"/resultsmiv2/{job_id}" if has_results else None
        }

        # If completed, add summary
        if has_results:
            summary = generate_summary(scout_account_id, application_name, job_id)
            if summary:
                response_body['summary'] = summary

        print(f"Status: {job_status}, Progress: {response_body['progress']}%")

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


def check_artifacts_exist(account_id: str, app_name: str, job_id: str) -> bool:
    """Check if all artifacts exist"""
    artifacts = [
        'static_monolith_analysis.json',
        'ai_pattern_analysis.json',
        'modularity_metrics.json',
        'detected_patterns.json',
        'decomposition_strategy.json'
    ]

    for artifact in artifacts:
        key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/{artifact}"
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        except:
            return False

    return True


def generate_summary(account_id: str, app_name: str, job_id: str) -> Dict[str, Any]:
    """Generate summary from artifacts"""
    try:
        # Read static analysis
        static_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
        static_data = json.loads(response['Body'].read().decode('utf-8'))

        # Read patterns
        patterns_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/detected_patterns.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=patterns_key)
        patterns_data = json.loads(response['Body'].read().decode('utf-8'))

        # Read modularity
        modularity_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/modularity_metrics.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=modularity_key)
        modularity_data = json.loads(response['Body'].read().decode('utf-8'))

        # Read decomposition
        decomp_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/decomposition_strategy.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=decomp_key)
        decomp_data = json.loads(response['Body'].read().decode('utf-8'))

        return {
            'total_programs_analyzed': static_data.get('total_programs', 0),
            'god_programs_detected': len(patterns_data.get('detected_patterns', {}).get('god_programs', [])),
            'high_coupling_programs': modularity_data.get('aggregate_metrics', {}).get('high_coupling_count', 0),
            'shared_copybooks': len(patterns_data.get('detected_patterns', {}).get('shared_data_hotspots', [])),
            'average_modularity_score': modularity_data.get('aggregate_metrics', {}).get('average_modularity', 0),
            'recommended_microservices': len(decomp_data.get('recommended_microservices', []))
        }

    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return None
