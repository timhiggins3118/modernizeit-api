"""
Java Generation V2 - Status API Handler
Lambda: JavaGenV2StatusAPI

Purpose: GET /statusjgv2/{job_id} - Return job status

V2 Design Principles:
- NO HARDCODING
- Standard V2 status API pattern
- Reads status.json from S3
"""

import json
import boto3
import os
from typing import Dict, Any

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get Java Generation V2 job status

    API Gateway Event:
    {
        "pathParameters": {
            "job_id": "jgv2_job_5150_TestApp01_1234567890_abc123"
        }
    }

    Response:
    {
        "job_id": "jgv2_job_...",
        "state": "running|completed|failed",
        "phase": "generating_services",
        "progress": 60,
        "message": "Generating service classes...",
        "started_at": "2025-10-04T10:00:00Z",
        "last_updated": "2025-10-04T10:05:00Z"
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - STATUS API")
        print("=" * 80)

        # Parse job_id from path parameters
        path_params = event.get('pathParameters', {})
        job_id = path_params.get('job_id', '')

        if not job_id:
            return error_response(400, 'Missing job_id parameter')

        if not job_id.startswith('jgv2_job_'):
            return error_response(400, 'Invalid job_id format (must start with jgv2_job_)')

        print(f"Job ID: {job_id}")

        # Parse job_id to get account and app
        # Format: jgv2_job_{account}_{app}_{timestamp}_{uuid}
        try:
            parts = job_id.split('_')
            if len(parts) < 5:
                raise ValueError("Invalid job_id format")

            scout_account_id = parts[2]
            application_name = parts[3]
            # timestamp = parts[4]
            # uuid = parts[5] if len(parts) > 5 else ''

        except Exception as e:
            print(f"ERROR parsing job_id: {str(e)}")
            return error_response(400, f'Invalid job_id format: {str(e)}')

        # Build S3 path
        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"
        status_key = f"{job_base}/status.json"

        print(f"Reading status from: {status_key}")

        # Read status from S3
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(response['Body'].read().decode('utf-8'))

            print(f"Status: {status_data.get('state')} / {status_data.get('phase')} ({status_data.get('progress')}%)")

            # Return status
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(status_data, indent=2)
            }

        except s3_client.exceptions.NoSuchKey:
            print(f"ERROR: Status file not found for job {job_id}")
            return error_response(404, f'Job not found: {job_id}')

        except Exception as e:
            print(f"ERROR reading status: {str(e)}")
            return error_response(500, f'Error reading job status: {str(e)}')

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Internal server error: {str(e)}')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Return error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message
        })
    }
