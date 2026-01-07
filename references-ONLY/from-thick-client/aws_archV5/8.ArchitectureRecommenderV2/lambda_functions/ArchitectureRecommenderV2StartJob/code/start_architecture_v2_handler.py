"""
Architecture Recommender V2 - Start Job Handler
Lambda: ArchitectureRecommenderV2StartJob

Purpose: API entry point to start architecture recommendation jobs

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Validates all V2 reports exist before starting
"""

import json
import boto3
import time
import uuid
import base64
from datetime import datetime, timezone
from typing import Dict, Any

s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

BUCKET_NAME = 'code-transformation-v2'
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:376129851858:stateMachine:ArchitectureRecommendationWorkflowV2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Start Architecture Recommendation Job

    Input (API Gateway):
    {
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "ar2_job_5150_TestApp01_...",
        "status": "pending",
        "workflow_execution_arn": "...",
        "next_steps": [...]
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - START JOB")
        print("=" * 80)

        # Parse input
        is_api_gateway = 'body' in event or 'requestContext' in event

        if 'body' in event:
            raw_body = event.get('body', '{}')

            # Handle base64 encoding
            if event.get('isBase64Encoded', False):
                raw_body = base64.b64decode(raw_body).decode('utf-8')

            if isinstance(raw_body, str):
                body = json.loads(raw_body) if raw_body.strip() else {}
            else:
                body = raw_body
        else:
            body = event

        scout_account_id = body.get('scout_account_id')
        application_name = body.get('application_name')

        if not scout_account_id:
            return error_response(400, 'Missing required field: scout_account_id', is_api_gateway)
        if not application_name:
            return error_response(400, 'Missing required field: application_name', is_api_gateway)

        print(f"Account: {scout_account_id}, App: {application_name}")

        base_path = f"{scout_account_id}/{application_name}"

        # Validate all required V2 reports exist
        print("\nValidating required V2 reports...")
        validation_errors = []

        # Check Discovery V2
        discovery_prefix = f"{base_path}/discovery_v2/jobs/"
        discovery_job = find_latest_job(discovery_prefix)
        if not discovery_job:
            validation_errors.append("Discovery V2 report not found. Please run Discovery V2 first.")
        else:
            print(f"✓ Discovery V2: {discovery_job}")

        # Check Data Analyzer V2
        data_prefix = f"{base_path}/data_analysis_v2/jobs/"
        data_job = find_latest_job(data_prefix)
        if not data_job:
            validation_errors.append("Data Analyzer V2 report not found. Please run Data Analyzer V2 first.")
        else:
            print(f"✓ Data Analyzer V2: {data_job}")

        # Check Code Analysis V3 (Nov 6, 2025: Updated to read V3 outputs)
        code_prefix = f"{base_path}/code_analysis_v3/jobs/"
        code_job = find_latest_job(code_prefix)
        if not code_job:
            validation_errors.append("Code Analysis V3 report not found. Please run Code Analysis V3 first.")
        else:
            print(f"✓ Code Analysis V3: {code_job}")

        # Check Refactor V2
        refactor_prefix = f"{base_path}/code_refactor_v2/jobs/"
        refactor_job = find_latest_job(refactor_prefix)
        if not refactor_job:
            validation_errors.append("Refactor V2 report not found. Please run Refactor V2 first.")
        else:
            print(f"✓ Refactor V2: {refactor_job}")

        if validation_errors:
            error_msg = "Missing required V2 reports: " + "; ".join(validation_errors)
            return error_response(400, error_msg, is_api_gateway)

        print("\n✓ All required V2 reports found!")

        # Generate job_id
        timestamp = int(time.time())
        job_uuid = str(uuid.uuid4())[:8]
        job_id = f"ar2_job_{scout_account_id}_{application_name}_{timestamp}_{job_uuid}"

        print(f"\nGenerated job_id: {job_id}")

        # Create job skeleton
        job_path = f"{base_path}/architecture_v2/jobs/{job_id}"

        job_info = {
            'job_id': job_id,
            'function': 'architecture_v2',
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'input_sources': {
                'discovery_v2': discovery_job,
                'data_analysis_v2': data_job,
                'code_analysis_v3': code_job,  # Nov 6, 2025: Updated to V3
                'code_refactor_v2': refactor_job
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
            'status': 'pending',
            'started_at': datetime.now(timezone.utc).isoformat(),
            'completed_at': None,
            'progress': 0,
            'phase': 'created',
            'message': 'Job initialized; waiting for architecture analysis.'
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/status.json",
            Body=json.dumps(status_info, indent=2),
            ContentType='application/json'
        )

        # Create artifacts directory
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/artifacts/_KEEP",
            Body=b'',
            ContentType='text/plain'
        )

        # Create execution_details.json (matches sample_outputs structure)
        execution_details = {
            'executionArn': None,  # Will be updated after Step Function starts
            'stateMachineArn': STATE_MACHINE_ARN,
            'name': f"execution-{job_id}",
            'status': 'PENDING',
            'startDate': datetime.now(timezone.utc).isoformat(),
            'stopDate': None,
            'input': json.dumps({
                'job_id': job_id,
                'scout_account_id': scout_account_id,
                'application_name': application_name,
                'discovery_job_id': discovery_job,
                'data_job_id': data_job,
                'code_job_id': code_job,
                'refactor_job_id': refactor_job
            }),
            'inputDetails': {
                'included': True
            },
            'output': None,
            'outputDetails': {
                'included': True
            }
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{job_path}/execution_details.json",
            Body=json.dumps(execution_details, indent=2),
            ContentType='application/json'
        )

        print(f"Job skeleton created: s3://{BUCKET_NAME}/{job_path}/")

        # Trigger Step Functions workflow
        execution_arn = None
        if is_api_gateway:
            try:
                print(f"\nTriggering Step Functions workflow...")
                sfn_response = sfn_client.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=f"execution-{job_id}",
                    input=json.dumps({
                        'job_id': job_id,
                        'scout_account_id': scout_account_id,
                        'application_name': application_name,
                        'discovery_job_id': discovery_job,
                        'data_job_id': data_job,
                        'code_job_id': code_job,
                        'refactor_job_id': refactor_job
                    })
                )
                execution_arn = sfn_response['executionArn']
                print(f"✓ Step Functions execution started: {execution_arn}")

                # Update execution_details.json with actual ARN
                execution_details['executionArn'] = execution_arn
                execution_details['status'] = 'RUNNING'
                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=f"{job_path}/execution_details.json",
                    Body=json.dumps(execution_details, indent=2),
                    ContentType='application/json'
                )
            except Exception as sfn_error:
                print(f"Warning: Failed to trigger Step Functions: {str(sfn_error)}")

        return success_response(job_id, job_path, execution_arn, is_api_gateway)

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}", is_api_gateway)


def find_latest_job(prefix: str) -> str:
    """Find the latest job ID in a given prefix"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/'
        )

        if 'CommonPrefixes' not in response:
            return None

        # Get all job directories
        job_dirs = [p['Prefix'].rstrip('/').split('/')[-1] for p in response['CommonPrefixes']]

        if not job_dirs:
            return None

        # Sort by timestamp (embedded in job_id)
        job_dirs.sort(reverse=True)

        return job_dirs[0]

    except Exception as e:
        print(f"Error finding latest job for {prefix}: {str(e)}")
        return None


def success_response(job_id: str, job_path: str, execution_arn: str, is_api_gateway: bool) -> Dict[str, Any]:
    """Build success response"""
    body_data = {
        'job_id': job_id,
        'status': 'pending',
        'workflow_execution_arn': execution_arn,
        'paths': {
            'job_root': f"s3://{BUCKET_NAME}/{job_path}/",
            'job_info': f"s3://{BUCKET_NAME}/{job_path}/job_info.json",
            'status': f"s3://{BUCKET_NAME}/{job_path}/status.json",
            'artifacts': f"s3://{BUCKET_NAME}/{job_path}/artifacts/"
        },
        'next_steps': [
            'Loading V2 reports (Discovery, Data, Code, Refactor)',
            'AI architecture analysis (Bedrock)',
            'Cost estimation (AWS Pricing API)',
            'Infrastructure as Code generation (CDK)',
            'Check status: GET /statusar2/{job_id}',
            'Get results: GET /resultsar2/{job_id}'
        ]
    }

    if is_api_gateway:
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(body_data, indent=2)
        }
    else:
        return {'statusCode': 201, 'body': body_data}


def error_response(status_code: int, message: str, is_api_gateway: bool) -> Dict[str, Any]:
    """Build error response"""
    error_data = {'error': message}

    if is_api_gateway:
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_data)
        }
    else:
        return {'statusCode': status_code, 'body': error_data}
