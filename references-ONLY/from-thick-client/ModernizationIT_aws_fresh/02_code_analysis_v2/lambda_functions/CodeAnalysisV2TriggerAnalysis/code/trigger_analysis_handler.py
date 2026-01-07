#!/usr/bin/env python3
"""
Code Analysis v2 - Trigger Analysis Handler
Triggers static analysis for a specific job
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Constants
BUCKET_NAME = 'code-transformation-v2'
PYTHON_ANALYZER_FUNCTION = 'CodeAnalysisV2StaticPython2'

def lambda_handler(event, context):
    """
    Trigger static analysis for a job
    """

    try:
        print(f"Trigger analysis request: {json.dumps(event.get('pathParameters', {}))}")

        # Parse job_id from path parameters
        path_params = event.get('pathParameters', {})
        job_id = path_params.get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id in path')

        print(f"Triggering analysis for job: {job_id}")

        # Step 1: Read job_info.json to get metadata
        # Extract account/app from job_id pattern: ca2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')
        if len(parts) < 5 or parts[0] != 'ca2' or parts[1] != 'job':
            return error_response(400, f'Invalid job_id format: {job_id}')

        scout_account_id = parts[2]
        # Handle multi-word app names (everything between account and timestamp)
        timestamp_index = -2  # timestamp is second-to-last
        application_name = '_'.join(parts[3:timestamp_index])

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_analysis_v2/jobs/{job_id}"

        print(f"Account: {scout_account_id}, App: {application_name}")

        # Read job_info.json
        job_info_key = f"{job_path}/job_info.json"
        try:
            response = s3_client.get_object(
                Bucket=BUCKET_NAME,
                Key=job_info_key
            )
            job_info = json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return error_response(404, f'Job not found: {job_id}')
            raise

        source_hash = job_info['source_hash']
        print(f"Found job with source_hash: {source_hash}")

        # Step 2: Update status.json to "running"
        status_info = {
            'state': 'running',
            'started_at': job_info.get('created_at'),
            'analysis_started_at': datetime.now(timezone.utc).isoformat(),
            'finished_at': None,
            'progress': 0.25,
            'message': 'Python static analysis in progress...',
            'phase': 'static_analysis'
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/status.json",
            Body=json.dumps(status_info, indent=2),
            ContentType='application/json'
        )
        print(f"Updated status to 'running'")

        # Step 3: Invoke Python analyzer asynchronously
        analyzer_payload = {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash
        }

        print(f"Invoking {PYTHON_ANALYZER_FUNCTION} with payload: {json.dumps(analyzer_payload)}")

        lambda_client.invoke(
            FunctionName=PYTHON_ANALYZER_FUNCTION,
            InvocationType='Event',  # Asynchronous
            Payload=json.dumps(analyzer_payload)
        )

        print(f"Analysis triggered successfully")

        return success_response(job_id, job_path)

    except Exception as e:
        print(f"Error triggering analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}")

def success_response(job_id, job_path):
    """Return success response"""
    return {
        'statusCode': 202,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Analysis started',
            'job_id': job_id,
            'status': 'running',
            'status_url': f"s3://{BUCKET_NAME}/{job_path}/status.json",
            'check_status': f"GET /codeanalysis2/{{job_id}}/status"
        }, indent=2)
    }

def error_response(status_code, message):
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
