"""
Java Generation V3 - Update Job Status Handler
Lambda: UpdateJobStatusV3

Purpose: Update job status to 'completed' after all flows finish

V3 Design Principles:
- NO HARDCODING
- NO SHARED CODE
- Updates status.json in S3
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, Any

s3_client = boto3.client('s3')

# Environment variables
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'code-transformation-v3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Update job status to completed

    Input:
    {
        "job_id": "jgv3_job_5150_TestApp01_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Updates status.json:
    {
        "state": "completed",
        "status": "completed",
        "phase": "finalized",
        "progress": 100,
        "message": "Java generation completed successfully",
        "last_updated": "2025-10-21T..."
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V3 - UPDATE JOB STATUS")
        print("=" * 80)

        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')

        if not all([job_id, scout_account_id, application_name]):
            raise ValueError("Missing required fields: job_id, scout_account_id, application_name")

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")

        # Build S3 path
        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"
        status_key = f"{job_base}/status.json"

        # Read current status
        try:
            response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=status_key)
            status_data = json.loads(response['Body'].read().decode('utf-8'))
            print(f"Current status: {status_data.get('state', 'unknown')}")
        except s3_client.exceptions.NoSuchKey:
            print("WARNING: status.json not found, creating new one")
            status_data = {}

        # Update to completed
        status_data['state'] = 'completed'
        status_data['status'] = 'completed'
        status_data['phase'] = 'finalized'
        status_data['progress'] = 100
        status_data['message'] = 'Java generation completed successfully'
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Write back to S3
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print("✓ Status updated to completed")

        return {
            'statusCode': 200,
            'job_id': job_id,
            'status': 'completed',
            'message': 'Status updated successfully'
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'error': str(e)
        }
