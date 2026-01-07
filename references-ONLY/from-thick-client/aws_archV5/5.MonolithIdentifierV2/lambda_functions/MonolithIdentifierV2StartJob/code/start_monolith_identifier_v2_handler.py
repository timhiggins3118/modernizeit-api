"""
Monolith Identifier V2 - Start Job Handler
Lambda: MonolithIdentifierV2StartJob

Purpose: Start monolith analysis job via API Gateway

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
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:376129851858:stateMachine:MonolithIdentifierWorkflowV2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Start Monolith Identifier V2 Job

    Input (from API Gateway):
    {
        "body": "{\"scout_account_id\": \"5150\", \"application_name\": \"TestApp01\"}"
    }

    Output:
    {
        "statusCode": 200,
        "body": "{\"job_id\": \"miv2_job_...\", ...}"
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - START JOB")
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
                    'error': 'No source code found',
                    'message': f'No uploads found for account {scout_account_id}, app {application_name}'
                })
            }

        print(f"Found source_hash: {source_hash}")

        # Generate job_id: miv2_job_{account}_{app}_{timestamp}_{uuid}
        timestamp = int(time.time())
        uuid_part = hashlib.md5(f"{scout_account_id}{application_name}{timestamp}".encode()).hexdigest()[:8]
        job_id = f"miv2_job_{scout_account_id}_{application_name}_{timestamp}_{uuid_part}"

        print(f"Generated job_id: {job_id}")

        # Create job metadata
        job_info = {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'pending',
            'workflow': 'MonolithIdentifierWorkflowV2'
        }

        # Write job_info.json
        job_info_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/job_info.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=job_info_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )
        print(f"Created job_info: s3://{BUCKET_NAME}/{job_info_key}")

        # Write initial status.json
        status = {
            'job_id': job_id,
            'state': 'running',
            'status': 'pending',
            'progress': 0,
            'phase': 'initialization',
            'message': 'Monolith analysis job started',
            'started_at': datetime.now(timezone.utc).isoformat()
        }

        status_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/status.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status, indent=2),
            ContentType='application/json'
        )
        print(f"Created status: s3://{BUCKET_NAME}/{status_key}")

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

        print(f"Started Step Functions execution: {sfn_response['executionArn']}")

        # Prepare response
        response_body = {
            'job_id': job_id,
            'source_hash': source_hash,
            'status': 'pending',
            'workflow_execution_arn': sfn_response['executionArn'],
            'paths': {
                'job_root': f"s3://{BUCKET_NAME}/{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/",
                'artifacts': f"s3://{BUCKET_NAME}/{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/"
            },
            'next_steps': [
                'Static analysis of COBOL programs',
                'AI-powered pattern detection',
                'Modularity metrics calculation',
                'Monolithic pattern detection',
                'Decomposition strategy generation',
                f'Check status: GET /statusmiv2/{job_id}',
                f'Get results: GET /resultsmiv2/{job_id}'
            ]
        }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body, indent=2)
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
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


def find_latest_source_hash(account_id: str, app_name: str) -> str:
    """Find the latest source_hash for the given account and app"""
    try:
        prefix = f"{account_id}/{app_name}/shared/uploads/"
        print(f"Searching for source_hash with prefix: {prefix}")

        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/'
        )

        if 'CommonPrefixes' not in response:
            print("No source hashes found")
            return None

        # Get all source_hash directories
        source_hashes = []
        for prefix_info in response['CommonPrefixes']:
            prefix_path = prefix_info['Prefix']
            source_hash = prefix_path.rstrip('/').split('/')[-1]
            source_hashes.append(source_hash)

        if not source_hashes:
            print("No source hashes found in CommonPrefixes")
            return None

        # Return the first one (they're typically sorted by S3)
        latest_hash = source_hashes[0]
        print(f"Found {len(source_hashes)} source hashes, using: {latest_hash}")

        return latest_hash

    except Exception as e:
        print(f"Error finding source_hash: {str(e)}")
        return None
