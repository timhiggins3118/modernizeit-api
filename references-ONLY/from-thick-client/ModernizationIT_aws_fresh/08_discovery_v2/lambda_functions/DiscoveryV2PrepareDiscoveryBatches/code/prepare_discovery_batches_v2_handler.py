"""
Discovery V2 - Prepare Discovery Batches Handler
Lambda: DiscoveryV2PrepareDiscoveryBatches

Purpose: Split COBOL files into batches for parallel AI discovery analysis

V2 Design Principles:
- Batch size: 5 files (SAME as Code Analysis V2)
- Reads from classified_catalog.json (from ingesting flow)
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'
BATCH_SIZE = 5  # Files per batch


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Prepare Discovery Batches

    Input (from Step Functions):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056..."
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056...",
        "total_files": 23,
        "total_batches": 5,
        "batches": [
            {
                "batch_id": 0,
                "files": ["file1.cbl", "file2.cbl", ...]
            },
            ...
        ]
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Preparing discovery batches for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'preparing_batches', 10, 'Preparing file batches for discovery analysis')

        # Read classified_catalog.json from shared location
        catalog_key = f"{scout_account_id}/{application_name}/shared/catalogs/{source_hash}/classified_catalog.json"

        try:
            catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
            catalog_data = json.loads(catalog_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"Classified catalog not found at s3://{BUCKET_NAME}/{catalog_key}")

        # Filter to COBOL files only
        cobol_files = catalog_data.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            raise Exception("No COBOL files found in classified catalog")

        # cobol_files is already a list of file paths
        file_paths = cobol_files

        print(f"Found {len(file_paths)} COBOL files to analyze")

        # Split into batches of 5 files each
        # NOTE: For Distributed Map, each batch item must include full context
        batches = []
        for i in range(0, len(file_paths), BATCH_SIZE):
            batch_files = file_paths[i:i + BATCH_SIZE]
            batches.append({
                'job_id': job_id,
                'scout_account_id': scout_account_id,
                'application_name': application_name,
                'source_hash': source_hash,
                'batch': {
                    'batch_id': len(batches),
                    'files': batch_files
                }
            })

        total_batches = len(batches)

        print(f"Created {total_batches} batches ({BATCH_SIZE} files per batch)")

        # Prepare output
        output = {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'total_files': len(file_paths),
            'total_batches': total_batches,
            'batches': batches
        }

        return output

    except Exception as e:
        print(f"ERROR in DiscoveryV2PrepareDiscoveryBatches: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update status to failed
        try:
            status_key = f"{event['scout_account_id']}/{event['application_name']}/discovery_v2/jobs/{event['job_id']}/status.json"
            update_status(status_key, 'failed', 'batch_preparation_failed', 0, f'Failed to prepare batches: {str(e)}')
        except:
            pass

        raise


def update_status(status_key: str, status: str, phase: str, progress: int, message: str):
    """Update job status in S3"""
    try:
        # Read current status
        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            status_data = {}

        # Update fields
        status_data['status'] = status
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        if status == 'failed':
            status_data['failed_at'] = datetime.now(timezone.utc).isoformat()

        # Write back
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {status} - {phase} ({progress}%) - {message}")

    except Exception as e:
        print(f"Failed to update status: {str(e)}")
