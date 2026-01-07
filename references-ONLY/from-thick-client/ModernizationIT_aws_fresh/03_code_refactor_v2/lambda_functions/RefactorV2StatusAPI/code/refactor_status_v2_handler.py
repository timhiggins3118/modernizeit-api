#!/usr/bin/env python3
"""
Code Refactor V2 - Status API Handler V2
Returns job status and recipe generation progress
"""

import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Return status for a refactor job
    GET /statusrf2/{job_id}
    """

    try:
        # Extract job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id')

        # Parse job_id: rf2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')

        if len(parts) < 6 or parts[0] != 'rf2' or parts[1] != 'job':
            return error_response(400, 'Invalid job_id format')

        scout_account_id = parts[2]

        # Find timestamp (second to last)
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        base_path = f"{scout_account_id}/{application_name}/code_refactor_v2/jobs/{job_id}"

        # Read status.json
        status_key = f"{base_path}/status.json"

        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return error_response(404, f'Job not found: {job_id}')
            raise

        # Calculate progress based on state
        state = status_data.get('state', 'unknown')
        phase = status_data.get('phase', 'unknown')

        progress_map = {
            'pending': 0,
            'pattern_detection': 30,
            'recipe_generation': 70,
            'completed': 100,
            'failed': -1
        }

        progress = progress_map.get(phase, 0)

        # Check if results exist
        results_key = f"{base_path}/artifacts/refactor_recipes.json"
        has_results = False

        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=results_key)
            has_results = True
        except ClientError:
            pass

        # Build response
        response_data = {
            'job_id': job_id,
            'status': state,
            'progress': progress,
            'phase': phase,
            'started_at': status_data.get('started_at'),
            'completed_at': status_data.get('completed_at'),
            'failed_at': status_data.get('failed_at'),
            'message': status_data.get('message', ''),
            'has_results': has_results,
            'results_url': f'/resultsrf2/{job_id}' if has_results else None
        }

        # Add error info if failed
        if state == 'failed':
            response_data['error_type'] = status_data.get('error_type')
            response_data['error'] = status_data.get('error')

        # Add recipe stats if available
        if has_results:
            try:
                results_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=results_key)
                results_data = json.loads(results_response['Body'].read().decode('utf-8'))
                summary = results_data.get('summary', {})

                response_data['recipes_generated'] = summary.get('total_recipes', 0)
                response_data['high_confidence_recipes'] = summary.get('high_confidence', 0)
            except Exception:
                pass  # Stats not critical

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }

    except Exception as e:
        print(f"Error retrieving status: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Internal error: {str(e)}')


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
