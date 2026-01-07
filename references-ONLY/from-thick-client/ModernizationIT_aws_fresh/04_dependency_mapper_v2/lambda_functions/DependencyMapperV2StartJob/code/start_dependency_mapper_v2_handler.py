"""
Dependency Mapper V2 - Start Job Handler
Lambda: DependencyMapperV2StartJob

Purpose: Start dependency analysis job via API Gateway

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
import base64
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any

s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

BUCKET_NAME = 'code-transformation-v2'
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:376129851858:stateMachine:DependencyMapperWorkflowV2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Start Dependency Mapper V2 Job

    Input (from API Gateway):
    {
        "body": "{\"scout_account_id\": \"5150\", \"application_name\": \"TestApp01\"}"
    }

    Output:
    {
        "statusCode": 200,
        "body": "{\"job_id\": \"dmv2_job_...\", ...}"
    }
    """
    try:
        print("=" * 80)
        print("DEPENDENCY MAPPER V2 - START JOB")
        print("=" * 80)

        # Parse request body (handle base64 encoding from API Gateway)
        body_str = event.get('body', '{}')

        if event.get('isBase64Encoded', False):
            body_str = base64.b64decode(body_str).decode('utf-8')

        request_body = json.loads(body_str)
        print(f"Request body: {json.dumps(request_body, indent=2)}")

        # Extract required parameters
        scout_account_id = request_body.get('scout_account_id')
        application_name = request_body.get('application_name')

        if not scout_account_id or not application_name:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing required parameters',
                    'required': ['scout_account_id', 'application_name']
                })
            }

        print(f"Account: {scout_account_id}, Application: {application_name}")

        # Find source_hash from shared/uploads
        source_hash = find_latest_source_hash(scout_account_id, application_name)

        if not source_hash:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'No source files found',
                    'message': f'No classified_catalog.json found in shared/catalogs for {scout_account_id}/{application_name}'
                })
            }

        print(f"Source hash: {source_hash}")

        # Generate job_id: dmv2_job_{account}_{app}_{timestamp}_{uuid}
        timestamp = int(time.time())
        uuid_part = hashlib.md5(f"{scout_account_id}{application_name}{timestamp}".encode()).hexdigest()[:8]
        job_id = f"dmv2_job_{scout_account_id}_{application_name}_{timestamp}_{uuid_part}"

        print(f"Generated job_id: {job_id}")

        # Create job paths
        job_root = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}"

        # Create job_info.json
        job_info = {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'workflow_execution_arn': '',  # Will be filled after starting workflow
            'status': 'pending'
        }

        job_info_key = f"{job_root}/job_info.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=job_info_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )
        print(f"Created job_info.json: s3://{BUCKET_NAME}/{job_info_key}")

        # Create status.json
        status_data = {
            'state': 'pending',
            'phase': 'initializing',
            'progress': 0,
            'message': 'Job created, waiting to start...',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }

        status_key = f"{job_root}/status.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )
        print(f"Created status.json: s3://{BUCKET_NAME}/{status_key}")

        # Start Step Functions workflow
        workflow_input = {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash
        }

        execution_name = f"execution-{job_id}"

        sfn_response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(workflow_input)
        )

        workflow_execution_arn = sfn_response['executionArn']
        print(f"Started Step Functions workflow: {workflow_execution_arn}")

        # Update job_info.json with workflow ARN
        job_info['workflow_execution_arn'] = workflow_execution_arn
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=job_info_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )

        # Build response
        response_body = {
            'job_id': job_id,
            'source_hash': source_hash,
            'status': 'pending',
            'workflow_execution_arn': workflow_execution_arn,
            'paths': {
                'job_root': f's3://{BUCKET_NAME}/{job_root}/',
                'artifacts': f's3://{BUCKET_NAME}/{job_root}/artifacts/'
            },
            'next_steps': [
                'Static analysis of COBOL source',
                'AI-powered dependency analysis',
                'Dependency graph generation',
                'Coupling metrics calculation',
                'Risk assessment',
                'Microservice boundary detection',
                f'Check status: GET /statusdmv2/{job_id}',
                f'Get results: GET /resultsdmv2/{job_id}'
            ]
        }

        print("=" * 80)
        print("DEPENDENCY MAPPER V2 JOB STARTED SUCCESSFULLY")
        print(f"Job ID: {job_id}")
        print("=" * 80)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body, indent=2)
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2StartJob: {str(e)}")
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


def find_latest_source_hash(scout_account_id: str, application_name: str) -> str:
    """Find the latest source_hash from shared/catalogs"""
    try:
        prefix = f"{scout_account_id}/{application_name}/shared/catalogs/"

        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/'
        )

        if 'CommonPrefixes' not in response:
            return ""

        # Get all source hashes (folder names)
        source_hashes = [
            cp['Prefix'].replace(prefix, '').rstrip('/')
            for cp in response['CommonPrefixes']
        ]

        # Check each for classified_catalog.json
        for source_hash in sorted(source_hashes, reverse=True):  # Most recent first
            catalog_key = f"{prefix}{source_hash}/classified_catalog.json"

            try:
                s3_client.head_object(Bucket=BUCKET_NAME, Key=catalog_key)
                print(f"Found classified_catalog.json for source_hash: {source_hash}")
                return source_hash
            except s3_client.exceptions.ClientError:
                continue

        return ""

    except Exception as e:
        print(f"Error finding source_hash: {str(e)}")
        return ""
