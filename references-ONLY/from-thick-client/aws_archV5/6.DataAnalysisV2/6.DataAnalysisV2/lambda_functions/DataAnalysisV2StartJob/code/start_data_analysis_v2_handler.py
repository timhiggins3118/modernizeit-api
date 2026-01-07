#!/usr/bin/env python3
"""
Data Analyzer V2 - Job Start Handler
Creates data analysis jobs and triggers DataAnalysisWorkflowV2
POST /prod/dataanalysis2
"""

import json
import boto3
import time
import uuid
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

BUCKET_NAME = 'code-transformation-v2'
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:376129851858:stateMachine:DataAnalysisWorkflowV2'

def lambda_handler(event, context):
    """
    Main handler for creating Data Analyzer V2 jobs
    POST /prod/dataanalysis2
    Body: {"scout_account_id": "5150", "application_name": "TestApp01"}
    """

    try:
        print(f"Data Analyzer V2 job creation request: {json.dumps(event.get('requestContext', {}))}")

        is_api_gateway = 'body' in event or 'requestContext' in event

        if 'body' in event:
            body = event.get('body', '{}')
            is_base64 = event.get('isBase64Encoded', False)

            if is_base64 and isinstance(body, str):
                import base64
                body = base64.b64decode(body).decode('utf-8')

            if not body or body == '':
                body = '{}'

            if isinstance(body, str):
                body = json.loads(body)
        else:
            body = event

        scout_account_id = body.get('scout_account_id')
        application_name = body.get('application_name')

        if not scout_account_id:
            return error_response(400, 'Missing required field: scout_account_id', is_api_gateway)
        if not application_name:
            return error_response(400, 'Missing required field: application_name', is_api_gateway)

        print(f"Creating data analysis job for account={scout_account_id}, app={application_name}")

        # Read latest.json to get current source_hash
        base_path = f"{scout_account_id}/{application_name}"
        latest_pointer_key = f"{base_path}/shared/uploads/latest.json"

        try:
            latest_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=latest_pointer_key)
            latest_data = json.loads(latest_response['Body'].read().decode('utf-8'))
            source_hash = latest_data['source_hash']
            print(f"Found current source_hash: {source_hash}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return error_response(404, f'No ingest data found for {scout_account_id}/{application_name}. Please run ingest flow first.', is_api_gateway)
            raise

        # Verify paths exist
        extracted_path = f"{base_path}/shared/uploads/{source_hash}/extracted/"
        classified_catalog_path = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"

        try:
            response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=extracted_path, MaxKeys=1)
            if response.get('KeyCount', 0) == 0:
                return error_response(404, f'No extracted files found at {extracted_path}', is_api_gateway)
        except ClientError as e:
            return error_response(500, f'Error checking extracted path: {str(e)}', is_api_gateway)

        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=classified_catalog_path)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return error_response(404, f'Classified catalog not found at {classified_catalog_path}', is_api_gateway)
            raise

        # Generate job_id (da2_job format)
        timestamp = int(time.time())
        job_uuid = str(uuid.uuid4())[:8]
        job_id = f"da2_job_{scout_account_id}_{application_name}_{timestamp}_{job_uuid}"
        print(f"Generated job_id: {job_id}")

        # Create job skeleton in S3
        job_path = f"{base_path}/data_analysis_v2/jobs/{job_id}"

        job_info = {
            'job_id': job_id,
            'function': 'data_analysis_v2',
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source_hash': source_hash,
            'ingest_paths': {
                'extracted': extracted_path,
                'classified_catalog': classified_catalog_path
            }
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/job_info.json",
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )

        status_info = {
            'state': 'pending',
            'started_at': datetime.now(timezone.utc).isoformat(),
            'finished_at': None,
            'progress': 0.0,
            'message': 'Job initialized; waiting for data analysis.',
            'phase': 'created'
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/status.json",
            Body=json.dumps(status_info, indent=2),
            ContentType='application/json'
        )

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/artifacts/_KEEP",
            Body=b'',
            ContentType='text/plain'
        )

        print(f"Job creation completed successfully: {job_id}")

        # Trigger Step Functions workflow
        execution_arn = None
        if is_api_gateway:
            try:
                print(f"Triggering Step Functions workflow for job: {job_id}")
                sfn_response = sfn_client.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=f"execution-{job_id}",
                    input=json.dumps({
                        'job_id': job_id,
                        'scout_account_id': scout_account_id,
                        'application_name': application_name,
                        'source_hash': source_hash
                    })
                )
                execution_arn = sfn_response['executionArn']
                print(f"Step Functions execution started: {execution_arn}")
            except Exception as sfn_error:
                print(f"Warning: Failed to trigger Step Functions: {str(sfn_error)}")

        return success_response(job_id, source_hash, base_path, job_path,
                              ingest_paths={'extracted': extracted_path, 'classified_catalog': classified_catalog_path},
                              execution_arn=execution_arn,
                              is_api_gateway=is_api_gateway)

    except Exception as e:
        print(f"Error creating data analysis job: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}", is_api_gateway)


def success_response(job_id, source_hash, base_path, job_path, ingest_paths, execution_arn=None, is_api_gateway=True):
    body_data = {
        'job_id': job_id,
        'source_hash': source_hash,
        'status': 'pending',
        'workflow_execution_arn': execution_arn,
        'paths': {
            'job_root': f"s3://{BUCKET_NAME}/{job_path}/",
            'job_info': f"s3://{BUCKET_NAME}/{job_path}/job_info.json",
            'status': f"s3://{BUCKET_NAME}/{job_path}/status.json",
            'artifacts': f"s3://{BUCKET_NAME}/{job_path}/artifacts/"
        },
        'next_steps': [
            'Data analysis (Regex, AST, AI)',
            'ERD generation',
            'Check status: GET /statusda2/{job_id}',
            'Get results: GET /resultsda2/{job_id}'
        ]
    }

    if is_api_gateway:
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(body_data, indent=2)
        }
    else:
        return {'statusCode': 201, 'body': body_data}


def error_response(status_code, message, is_api_gateway=True):
    error_data = {'error': message}
    if is_api_gateway:
        return {
            'statusCode': status_code,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(error_data)
        }
    else:
        return {'statusCode': status_code, 'body': error_data}
