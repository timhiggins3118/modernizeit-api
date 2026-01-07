"""
Dependency Mapper V2 - Prepare Analysis Handler
Lambda: DependencyMapperV2PrepareAnalysis

Purpose: Prepare COBOL files for dependency analysis

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'
BATCH_SIZE = 5  # Files per batch for parallel processing


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Prepare Dependency Analysis

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_5150_TestApp01_1759500000_abc123de",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056..."
    }

    Output:
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056...",
        "total_files": 23,
        "total_batches": 5,
        "batches": [
            {
                "job_id": "dmv2_job_...",
                "scout_account_id": "5150",
                "application_name": "TestApp01",
                "source_hash": "21a056...",
                "batch": {
                    "batch_id": 0,
                    "files": ["Labs/cbl/ORD001.cobol", ...]
                }
            }
        ]
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Preparing dependency analysis for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'preparing_analysis', 10, 'Preparing COBOL files for analysis')

        # Read classified_catalog.json
        catalog_key = f"{scout_account_id}/{application_name}/shared/catalogs/{source_hash}/classified_catalog.json"

        try:
            catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
            catalog_data = json.loads(catalog_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"Classified catalog not found at s3://{BUCKET_NAME}/{catalog_key}")

        print(f"Read classified catalog: {len(catalog_data.get('classifications', {}))} classifications")

        # Filter to COBOL files only
        cobol_files = catalog_data.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            raise Exception("No COBOL files found in classified catalog")

        print(f"Found {len(cobol_files)} COBOL files for dependency analysis")

        # Create batches (5 files per batch) for parallel static analysis
        # NOTE: For Distributed Map, each batch item must include full context
        batches = []
        for i in range(0, len(cobol_files), BATCH_SIZE):
            batch_files = cobol_files[i:i + BATCH_SIZE]
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

        print(f"Created {len(batches)} batches for parallel processing")

        # Update status
        update_status(status_key, 'running', 'preparing_analysis', 15, f'Prepared {len(batches)} batches for static analysis')

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'total_files': len(cobol_files),
            'total_batches': len(batches),
            'batches': batches
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2PrepareAnalysis: {str(e)}")
        import traceback
        traceback.print_exc()
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
        status_data['state'] = status
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

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
