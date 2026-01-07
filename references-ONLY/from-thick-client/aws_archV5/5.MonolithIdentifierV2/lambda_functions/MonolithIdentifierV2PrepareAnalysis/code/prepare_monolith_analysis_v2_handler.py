"""
Monolith Identifier V2 - Prepare Analysis Handler
Lambda: MonolithIdentifierV2PrepareAnalysis

Purpose: Prepare COBOL files into batches for parallel processing

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Reads from classified catalog
"""

import json
import boto3
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'
BATCH_SIZE = 10  # Programs per batch


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Prepare Monolith Analysis - Create batches for parallel processing

    Input:
    {
        "job_id": "miv2_job_5150_TestApp01_1759500000_abc123de",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056207887..."
    }

    Output:
    {
        "job_id": "miv2_job_...",
        "total_programs": 87,
        "batches": [
            {"batch_id": 0, "files": ["file1.cbl", ...]},
            ...
        ]
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - PREPARE ANALYSIS")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")
        print(f"Source Hash: {source_hash}")

        # Read classified catalog
        catalog_key = f"{scout_account_id}/{application_name}/shared/catalogs/{source_hash}/classified_catalog.json"
        print(f"Reading catalog: s3://{BUCKET_NAME}/{catalog_key}")

        catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
        catalog_data = json.loads(catalog_response['Body'].read().decode('utf-8'))

        print(f"Catalog has {len(catalog_data.get('classifications', {}))} classifications")

        # Filter for COBOL files
        cobol_files = catalog_data.get('classifications', {}).get('cobol', [])

        print(f"Found {len(cobol_files)} COBOL files")

        if not cobol_files:
            raise ValueError("No COBOL files found in classified catalog")

        # Create batches (include all context for Distributed Map)
        batches = []
        for i in range(0, len(cobol_files), BATCH_SIZE):
            batch = {
                'job_id': job_id,
                'scout_account_id': scout_account_id,
                'application_name': application_name,
                'source_hash': source_hash,
                'batch_id': len(batches),
                'files': cobol_files[i:i + BATCH_SIZE]
            }
            batches.append(batch)

        print(f"Created {len(batches)} batches of up to {BATCH_SIZE} files each")

        # Write batch configuration
        batch_config = {
            'job_id': job_id,
            'total_programs': len(cobol_files),
            'total_batches': len(batches),
            'batch_size': BATCH_SIZE,
            'batches': batches
        }

        batch_config_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/batch_config.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=batch_config_key,
            Body=json.dumps(batch_config, indent=2),
            ContentType='application/json'
        )

        print(f"Wrote batch config: s3://{BUCKET_NAME}/{batch_config_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'preparing_batches',
            'progress': 10,
            'message': f'Prepared {len(batches)} batches for {len(cobol_files)} programs'
        })

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'total_programs': len(cobol_files),
            'total_batches': len(batches),
            'batches': batches
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def update_status(account_id: str, app_name: str, job_id: str, updates: Dict[str, Any]):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/status.json"

        # Read current status
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status = json.loads(response['Body'].read().decode('utf-8'))

        # Apply updates
        status.update(updates)

        # Write back
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status, indent=2),
            ContentType='application/json'
        )

        print(f"Updated status: {updates}")

    except Exception as e:
        print(f"Error updating status: {str(e)}")
