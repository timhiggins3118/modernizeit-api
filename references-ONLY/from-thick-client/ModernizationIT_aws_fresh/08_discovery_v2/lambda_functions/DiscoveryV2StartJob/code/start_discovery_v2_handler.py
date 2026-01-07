"""
Discovery V2 - Start Job Handler
Lambda: DiscoveryV2StartJob

API Endpoint: POST /discovery2
Purpose: Creates discovery job, triggers Step Functions workflow

V2 Design Principles:
- NO file upload (reads from ingesting flow)
- Uses code-transformation-v2 bucket
- Follows Code Analysis V2 pattern
- Independent Lambda (NO code sharing)
"""

import json
import boto3
import uuid
import base64
from datetime import datetime, timezone
from typing import Dict, Any

s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

BUCKET_NAME = 'code-transformation-v2'
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:376129851858:stateMachine:DiscoveryWorkflowV2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Start Discovery V2 Job

    Input (API Gateway POST):
    {
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "source_hash": "21a056...",
        "status": "pending",
        "workflow_execution_arn": "arn:aws:states:...",
        "paths": {...}
    }
    """
    try:
        # Parse request body
        body = event.get('body')

        if body is None:
            # Try direct event access (Step Functions or direct invoke)
            body = event
        elif isinstance(body, str):
            # Check if base64 encoded (API Gateway sometimes does this)
            if event.get('isBase64Encoded', False):
                body = base64.b64decode(body).decode('utf-8')

            # API Gateway sends body as string
            if body.strip():
                body = json.loads(body)
            else:
                body = event

        scout_account_id = body.get('scout_account_id')
        application_name = body.get('application_name')

        # Validation
        if not scout_account_id or not application_name:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing required fields: scout_account_id, application_name'
                })
            }

        # Read latest.json from shared location to get source_hash
        latest_key = f"{scout_account_id}/{application_name}/shared/uploads/latest.json"

        try:
            latest_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=latest_key)
            latest_data = json.loads(latest_response['Body'].read())
            source_hash = latest_data['source_hash']
        except s3_client.exceptions.NoSuchKey:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'No uploaded files found',
                    'message': f'Please upload files first using the ingesting flow',
                    'expected_path': f's3://{BUCKET_NAME}/{latest_key}'
                })
            }
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Failed to read source files',
                    'message': str(e)
                })
            }

        # Generate job ID: dv2_job_{account}_{app}_{timestamp}_{uuid}
        timestamp = int(datetime.now(timezone.utc).timestamp())
        uuid_part = str(uuid.uuid4())[:8]
        job_id = f"dv2_job_{scout_account_id}_{application_name}_{timestamp}_{uuid_part}"

        # S3 paths
        job_root = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}"
        job_info_key = f"{job_root}/job_info.json"
        status_key = f"{job_root}/status.json"
        artifacts_prefix = f"{job_root}/artifacts/"

        # Create job_info.json
        job_info = {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': 'DiscoveryV2StartJob',
            'flow_type': 'discovery_v2',
            'source_location': f's3://{BUCKET_NAME}/{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/'
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=job_info_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )

        # Create status.json
        status_data = {
            'job_id': job_id,
            'status': 'pending',
            'phase': 'initialization',
            'progress': 0,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'completed_at': None,
            'failed_at': None,
            'message': 'Discovery job created, workflow starting',
            'last_updated': datetime.now(timezone.utc).isoformat()
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

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

        # Response
        response_data = {
            'job_id': job_id,
            'source_hash': source_hash,
            'status': 'pending',
            'workflow_execution_arn': workflow_execution_arn,
            'paths': {
                'job_root': f's3://{BUCKET_NAME}/{job_root}/',
                'job_info': f's3://{BUCKET_NAME}/{job_info_key}',
                'status': f's3://{BUCKET_NAME}/{status_key}',
                'artifacts': f's3://{BUCKET_NAME}/{artifacts_prefix}'
            },
            'next_steps': [
                'AI discovery analysis (batched)',
                'Business process extraction',
                'Integration point detection',
                'API pattern analysis',
                'ROI calculation',
                'Migration roadmap generation',
                f'Check status: GET /statusdv2/{job_id}',
                f'Get results: GET /resultsdv2/{job_id}'
            ]
        }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_data, indent=2)
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2StartJob: {str(e)}")
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
