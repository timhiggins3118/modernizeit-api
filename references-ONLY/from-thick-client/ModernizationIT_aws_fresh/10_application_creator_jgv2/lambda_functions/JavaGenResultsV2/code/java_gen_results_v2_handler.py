"""
Java Generation V2 - Results API Handler
Lambda: JavaGenV2ResultsAPI

Purpose: GET /resultsjgv2/{job_id} - Return job results and download URL

V2 Design Principles:
- NO HARDCODING
- Standard V2 results API pattern
- Returns validation report + presigned download URL
"""

import json
import boto3
import os
from typing import Dict, Any

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')
PRESIGNED_URL_EXPIRATION = int(os.environ.get('PRESIGNED_URL_EXPIRATION', '3600'))  # 1 hour


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get Java Generation V2 job results

    API Gateway Event:
    {
        "pathParameters": {
            "job_id": "jgv2_job_5150_TestApp01_1234567890_abc123"
        }
    }

    Response:
    {
        "job_id": "jgv2_job_...",
        "status": "completed",
        "validation_report": {...},
        "download_url": "https://s3.amazonaws.com/...",
        "download_expires_in": 3600
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - RESULTS API")
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
        try:
            parts = job_id.split('_')
            if len(parts) < 5:
                raise ValueError("Invalid job_id format")

            scout_account_id = parts[2]
            application_name = parts[3]

        except Exception as e:
            print(f"ERROR parsing job_id: {str(e)}")
            return error_response(400, f'Invalid job_id format: {str(e)}')

        # Build S3 paths
        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        status_key = f"{job_base}/status.json"
        validation_report_key = f"{job_base}/validation_report.json"
        zip_key = f"{job_base}/artifacts/generated_project.zip"

        # Check if job is completed
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(response['Body'].read().decode('utf-8'))

            job_state = status_data.get('state', '')

            if job_state != 'completed':
                return error_response(400, f'Job not completed yet. Current state: {job_state}')

        except s3_client.exceptions.NoSuchKey:
            return error_response(404, f'Job not found: {job_id}')
        except Exception as e:
            return error_response(500, f'Error reading job status: {str(e)}')

        # Read validation report
        validation_report = {}
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=validation_report_key)
            validation_report = json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"WARNING: Could not read validation report: {str(e)}")

        # Check if ZIP exists
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=zip_key)
        except s3_client.exceptions.NoSuchKey:
            return error_response(404, 'Generated project ZIP not found')
        except Exception as e:
            return error_response(500, f'Error checking ZIP file: {str(e)}')

        # Generate presigned URL for ZIP download
        print(f"Generating presigned URL for: {zip_key}")

        try:
            download_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': BUCKET_NAME,
                    'Key': zip_key
                },
                ExpiresIn=PRESIGNED_URL_EXPIRATION
            )

            print("✓ Presigned URL generated")

        except Exception as e:
            print(f"ERROR generating presigned URL: {str(e)}")
            return error_response(500, f'Error generating download URL: {str(e)}')

        # Build results response
        results = {
            'job_id': job_id,
            'status': 'completed',
            'application_name': application_name,
            'validation_report': validation_report,
            'download_url': download_url,
            'download_expires_in_seconds': PRESIGNED_URL_EXPIRATION,
            'zip_location': f"s3://{BUCKET_NAME}/{zip_key}",
            'message': 'Java generation completed successfully! Download the ZIP to get your modernized Spring Boot application.'
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(results, indent=2)
        }

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
