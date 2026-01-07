"""
Discovery V2 - Status API Handler
Lambda: DiscoveryV2StatusAPI

API Endpoint: GET /statusdv2/{job_id}
Purpose: Check discovery job status

V2 Design Principles:
- Simple status lookup
- Returns progress percentage and phase
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Check Discovery Job Status

    Input (API Gateway GET):
    Path: /statusdv2/{job_id}

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "status": "completed",
        "progress": 100,
        "phase": "completed",
        "message": "Discovery analysis completed successfully",
        "has_results": true,
        "results_url": "/resultsdv2/dv2_job_5150_TestApp01_1759440123_a7b3c9d2"
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

        # Validate job_id format (dv2_job_...)
        if not job_id.startswith('dv2_job_'):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid job_id format. Must start with dv2_job_'
                })
            }

        # Parse job_id to get account and app
        # Format: dv2_job_{account}_{app}_{timestamp}_{uuid}
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

        # Read status.json
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"

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

        # Check if results exist (discovery_report.json or migration_roadmap.json)
        has_results = False

        if status_data.get('state') == 'completed':
            report_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/discovery_report.json"

            try:
                s3_client.head_object(Bucket=BUCKET_NAME, Key=report_key)
                has_results = True
            except:
                has_results = False

        # Build response
        response_data = {
            'job_id': job_id,
            'status': status_data.get('state', 'unknown'),  # Step Functions uses 'state' not 'status'
            'progress': status_data.get('progress', 0),
            'phase': status_data.get('phase', 'unknown'),
            'started_at': status_data.get('started_at'),
            'completed_at': status_data.get('completed_at'),
            'failed_at': status_data.get('failed_at'),
            'message': status_data.get('message', ''),
            'has_results': has_results,
            'results_url': f"/resultsdv2/{job_id}" if has_results else None
        }

        # Add summary stats if available
        if has_results:
            try:
                # Try to read business processes to get count
                bp_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/business_processes.json"
                bp_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=bp_key)
                bp_data = json.loads(bp_response['Body'].read())
                response_data['business_processes_discovered'] = bp_data.get('summary', {}).get('total_processes', 0)

                # Try to read integration points to get count
                int_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/integration_points.json"
                int_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=int_key)
                int_data = json.loads(int_response['Body'].read())
                response_data['integration_points_discovered'] = int_data.get('summary', {}).get('total_integration_points', 0)

                # Try to read API pattern
                api_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/api_patterns.json"
                api_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=api_key)
                api_data = json.loads(api_response['Body'].read())
                response_data['api_pattern_detected'] = api_data.get('primary_api_pattern', 'unknown')

            except:
                pass  # Stats are optional

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_data, indent=2)
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2StatusAPI: {str(e)}")
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
