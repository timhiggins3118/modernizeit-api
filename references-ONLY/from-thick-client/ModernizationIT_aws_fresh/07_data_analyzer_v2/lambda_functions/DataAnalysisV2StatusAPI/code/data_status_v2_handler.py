#!/usr/bin/env python3
"""
Data Analyzer V2 - Status API Handler
Returns job status and ERD generation progress
GET /statusda2/{job_id}
"""

import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Return status for a data analysis job
    GET /statusda2/{job_id}
    """

    try:
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id')

        # Parse job_id: da2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')

        if len(parts) < 6 or parts[0] != 'da2' or parts[1] != 'job':
            return error_response(400, 'Invalid job_id format')

        scout_account_id = parts[2]
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/data_analysis_v2/jobs/{job_id}"

        # Read status.json
        status_key = f"{job_path}/status.json"

        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return error_response(404, f'Job not found: {job_id}')
            raise

        # Calculate progress
        state = status_data.get('state', 'unknown')
        phase = status_data.get('phase', 'unknown')

        progress_map = {
            'pending': 0,
            'data_analysis': 40,
            'erd_generation': 80,
            'completed': 100,
            'failed': -1
        }

        progress = progress_map.get(phase, 0)

        # Check if ERD exists
        erd_key = f"{job_path}/artifacts/erd.json"
        has_results = False
        entities_discovered = 0
        relationships_discovered = 0

        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=erd_key)
            has_results = True

            # Read ERD to get entity/relationship counts
            erd_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=erd_key)
            erd_data = json.loads(erd_response['Body'].read().decode('utf-8'))
            summary = erd_data.get('summary', {})
            entities_discovered = summary.get('total_entities', 0)
            relationships_discovered = summary.get('total_relationships', 0)
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
            'results_url': f'/resultsda2/{job_id}' if has_results else None,
            'entities_discovered': entities_discovered,
            'relationships_discovered': relationships_discovered
        }

        # Add error info if failed
        if state == 'failed':
            response_data['error_type'] = status_data.get('error_type')
            response_data['error'] = status_data.get('error')

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(response_data)
        }

    except Exception as e:
        print(f"Error retrieving status: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Internal error: {str(e)}')


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'error': message})
    }
