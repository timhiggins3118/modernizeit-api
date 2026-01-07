#!/usr/bin/env python3
"""
Code Analysis V2 - Status API Handler
Returns job status and metadata
"""

import json
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    GET /statusv2/{job_id}
    Returns job status and progress information
    """

    try:
        # Extract job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id in path')

        # Parse job_id to extract account and app
        # Format: ca2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')
        if len(parts) < 5 or parts[0] != 'ca2' or parts[1] != 'job':
            return error_response(400, f'Invalid job_id format: {job_id}')

        scout_account_id = parts[2]
        # Find application_name (everything between account and timestamp)
        timestamp_idx = -2  # timestamp is second to last
        application_name = '_'.join(parts[3:timestamp_idx])

        print(f"Status request for job: {job_id}, account: {scout_account_id}, app: {application_name}")

        # Read job_info.json
        job_info_key = f"{scout_account_id}/{application_name}/code_analysis_v2/jobs/{job_id}/job_info.json"
        try:
            job_info_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=job_info_key)
            job_info = json.loads(job_info_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return error_response(404, f'Job not found: {job_id}')
            raise

        # Read status.json
        status_key = f"{scout_account_id}/{application_name}/code_analysis_v2/jobs/{job_id}/status.json"
        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # If no status file, job is still pending
                status_data = {
                    'state': 'pending',
                    'phase': 'created',
                    'message': 'Job initialized'
                }
            else:
                raise

        # Calculate progress percentage
        progress = 0
        if status_data.get('state') == 'completed':
            progress = 100
        elif status_data.get('state') == 'failed':
            progress = 0
        elif status_data.get('phase') == 'static_analysis':
            progress = 50
        elif status_data.get('phase') == 'created':
            progress = 10

        # Check if results exist
        has_results = False
        results_location = None
        if status_data.get('state') == 'completed' and status_data.get('outputs', {}).get('static_analysis'):
            has_results = True
            results_location = status_data['outputs']['static_analysis']

        # Build response
        response_data = {
            'job_id': job_id,
            'status': status_data.get('state', 'unknown'),
            'stage': status_data.get('phase', 'unknown'),
            'progress': progress,
            'message': status_data.get('message', 'Processing...'),
            'created_at': job_info.get('created_at'),
            'updated_at': status_data.get('completed_at') or status_data.get('failed_at') or status_data.get('started_at'),
            'pipeline': 'code_analysis_v2',
            'has_results': has_results,
            'results_location': results_location,
            'results_url': f"/resultsv2/{job_id}" if has_results else None,
            'source_hash': job_info.get('source_hash'),
            'analyzers': ['regex', 'tree-sitter'],
            'estimated_remaining': '0 minutes' if status_data.get('state') == 'completed' else 'Processing...'
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data, indent=2)
        }

    except Exception as e:
        print(f"Error getting job status: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}")


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
