#!/usr/bin/env python3
"""
Code Analysis v2 - Job Creation Handler
Creates analysis jobs and reads from Ingest Flow's canonical structure
"""

import json
import boto3
import time
import uuid
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

# Constants
BUCKET_NAME = 'code-transformation-v2'
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:376129851858:stateMachine:CodeAnalysisWorkflowV2'

def lambda_handler(event, context):
    """
    Main handler for creating Code Analysis v2 jobs
    Reads from Ingest Flow's shared/ structure
    """

    try:
        print(f"Code Analysis v2 job creation request: {json.dumps(event.get('requestContext', {}))}")

        # Detect invocation source (API Gateway vs Step Functions)
        is_api_gateway = 'body' in event or 'requestContext' in event

        # Parse input - handle BOTH API Gateway format AND direct Step Functions format
        if 'body' in event:
            # API Gateway format
            body = event.get('body', '{}')
            is_base64 = event.get('isBase64Encoded', False)

            print(f"DEBUG: Raw body type: {type(body)}")
            print(f"DEBUG: isBase64Encoded: {is_base64}")

            # Decode base64 if needed (API Gateway binary media types)
            if is_base64 and isinstance(body, str):
                import base64
                body = base64.b64decode(body).decode('utf-8')
                print(f"DEBUG: Decoded body: {body}")

            if not body or body == '':
                body = '{}'

            if isinstance(body, str):
                body = json.loads(body)
        else:
            # Direct Step Functions invocation format
            body = event

        # Validate required fields
        scout_account_id = body.get('scout_account_id')
        application_name = body.get('application_name')

        if not scout_account_id:
            return error_response(400, 'Missing required field: scout_account_id', is_api_gateway)
        if not application_name:
            return error_response(400, 'Missing required field: application_name', is_api_gateway)

        print(f"Creating analysis job for account={scout_account_id}, app={application_name}")

        # Step 1: Read latest.json to get current source_hash
        base_path = f"{scout_account_id}/{application_name}"
        latest_pointer_key = f"{base_path}/shared/uploads/latest.json"

        try:
            latest_response = s3_client.get_object(
                Bucket=BUCKET_NAME,
                Key=latest_pointer_key
            )
            latest_data = json.loads(latest_response['Body'].read().decode('utf-8'))
            source_hash = latest_data['source_hash']
            print(f"Found current source_hash: {source_hash}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return error_response(404, f'No ingest data found for {scout_account_id}/{application_name}. Please run ingest flow first.', is_api_gateway)
            raise

        # Step 2: Verify ingest paths exist
        extracted_path = f"{base_path}/shared/uploads/{source_hash}/extracted/"
        file_catalog_path = f"{base_path}/shared/catalogs/{source_hash}/file_catalog.json"
        classified_catalog_path = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"

        # Check extracted/ directory exists (check for any file in it)
        try:
            response = s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                Prefix=extracted_path,
                MaxKeys=1
            )
            if response.get('KeyCount', 0) == 0:
                return error_response(404, f'No extracted files found at {extracted_path}', is_api_gateway)
            print(f"Verified extracted files exist at {extracted_path}")
        except ClientError as e:
            return error_response(500, f'Error checking extracted path: {str(e)}', is_api_gateway)

        # Check file_catalog.json exists
        try:
            s3_client.head_object(
                Bucket=BUCKET_NAME,
                Key=file_catalog_path
            )
            print(f"Verified file_catalog.json exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return error_response(404, f'File catalog not found at {file_catalog_path}', is_api_gateway)
            raise

        # Check classified_catalog.json exists
        try:
            s3_client.head_object(
                Bucket=BUCKET_NAME,
                Key=classified_catalog_path
            )
            print(f"Verified classified_catalog.json exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return error_response(404, f'Classified catalog not found at {classified_catalog_path}', is_api_gateway)
            raise

        # Step 3: Generate job_id
        timestamp = int(time.time())
        job_uuid = str(uuid.uuid4())[:8]
        job_id = f"ca2_job_{scout_account_id}_{application_name}_{timestamp}_{job_uuid}"
        print(f"Generated job_id: {job_id}")

        # Step 4: Create job skeleton in S3
        job_path = f"{base_path}/code_analysis_v2/jobs/{job_id}"

        # Create job_info.json
        job_info = {
            'job_id': job_id,
            'function': 'code_analysis_v2',
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source_hash': source_hash,
            'ingest_paths': {
                'extracted': extracted_path,
                'file_catalog': file_catalog_path,
                'classified_catalog': classified_catalog_path
            }
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/job_info.json",
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )
        print(f"Created job_info.json")

        # Create status.json
        status_info = {
            'state': 'pending',
            'started_at': datetime.now(timezone.utc).isoformat(),
            'finished_at': None,
            'progress': 0.0,
            'message': 'Job initialized; waiting for static analysis.',
            'phase': 'created'
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/status.json",
            Body=json.dumps(status_info, indent=2),
            ContentType='application/json'
        )
        print(f"Created status.json")

        # Create input_ref.json
        input_ref = {
            'source_hash': source_hash,
            'extracted_path': extracted_path,
            'file_catalog_path': file_catalog_path,
            'classified_catalog_path': classified_catalog_path,
            'artifacts_root': f"{job_path}/artifacts/"
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/input_ref.json",
            Body=json.dumps(input_ref, indent=2),
            ContentType='application/json'
        )
        print(f"Created input_ref.json")

        # Create artifacts/_KEEP placeholder
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/artifacts/_KEEP",
            Body=b'',
            ContentType='text/plain'
        )
        print(f"Created artifacts/ directory")

        print(f"Job creation completed successfully: {job_id}")

        # Trigger Step Functions workflow for analysis
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
                print(f"Step Functions execution started: {sfn_response['executionArn']}")
            except Exception as sfn_error:
                print(f"Warning: Failed to trigger Step Functions: {str(sfn_error)}")
                # Don't fail the job creation if Step Functions trigger fails

        return success_response(job_id, source_hash, base_path, job_path, ingest_paths={
            'extracted': extracted_path,
            'file_catalog': file_catalog_path,
            'classified_catalog': classified_catalog_path
        }, is_api_gateway=is_api_gateway)

    except Exception as e:
        print(f"Error creating analysis job: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}", is_api_gateway)

def success_response(job_id, source_hash, base_path, job_path, ingest_paths, is_api_gateway=True):
    """
    Return success response
    Format depends on invocation source (API Gateway vs Step Functions)
    """
    body_data = {
        'job_id': job_id,
        'source_hash': source_hash,
        'status': 'pending',
        'paths': {
            'job_root': f"s3://{BUCKET_NAME}/{job_path}/",
            'job_info': f"s3://{BUCKET_NAME}/{job_path}/job_info.json",
            'status': f"s3://{BUCKET_NAME}/{job_path}/status.json",
            'artifacts': f"s3://{BUCKET_NAME}/{job_path}/artifacts/"
        },
        'ingest_paths': {
            'extracted': f"s3://{BUCKET_NAME}/{ingest_paths['extracted']}",
            'file_catalog': f"s3://{BUCKET_NAME}/{ingest_paths['file_catalog']}",
            'classified_catalog': f"s3://{BUCKET_NAME}/{ingest_paths['classified_catalog']}"
        },
        'next': [
            'Phase 2: Static analysis (Docker Lambda)',
            'Phase 3: Bedrock AI analysis',
            'Phase 4: Report generation'
        ]
    }

    if is_api_gateway:
        # API Gateway format - return statusCode + headers + body as JSON string
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(body_data, indent=2)
        }
    else:
        # Step Functions format - return data directly
        return {
            'statusCode': 201,
            'body': body_data
        }

def error_response(status_code, message, is_api_gateway=True):
    """
    Return error response
    Format depends on invocation source (API Gateway vs Step Functions)
    """
    error_data = {'error': message}

    if is_api_gateway:
        # API Gateway format - return statusCode + headers + body as JSON string
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_data)
        }
    else:
        # Step Functions format - return data directly
        return {
            'statusCode': status_code,
            'body': error_data
        }