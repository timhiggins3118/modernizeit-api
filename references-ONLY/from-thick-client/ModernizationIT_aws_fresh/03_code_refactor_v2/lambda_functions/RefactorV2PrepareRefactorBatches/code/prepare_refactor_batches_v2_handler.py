#!/usr/bin/env python3
"""
Code Refactor V2 - Prepare Refactor Batches V2
Splits COBOL files into processable batches for parallel AI pattern analysis
"""

import json
import boto3
from math import ceil

s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'
BATCH_SIZE = 5  # Files per batch

def lambda_handler(event, context):
    """
    Prepare batches of COBOL files for parallel AI pattern analysis
    Reads classified catalog and splits files into batches
    """

    try:
        print(f"PrepareRefactorBatchesV2 starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        base_path = f"{scout_account_id}/{application_name}"

        # Read classified catalog to get COBOL files
        catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            print("No COBOL files found in catalog")
            return {
                'statusCode': 200,
                'body': {
                    'status': 'completed',
                    'batches': [],
                    'total_batches': 0,
                    'total_files': 0,
                    'message': 'No COBOL files to analyze for patterns'
                }
            }

        print(f"Found {len(cobol_files)} COBOL files to batch for pattern analysis")

        # Create batches
        batches = []
        total_files = len(cobol_files)
        total_batches = ceil(total_files / BATCH_SIZE)

        for i in range(0, total_files, BATCH_SIZE):
            batch_files = cobol_files[i:i + BATCH_SIZE]
            batch_id = i // BATCH_SIZE

            batches.append({
                'batch_id': batch_id,
                'files': batch_files,
                'file_count': len(batch_files)
            })

            print(f"Batch {batch_id}: {len(batch_files)} files")

        print(f"Created {len(batches)} batches for pattern analysis of {total_files} files")

        # Return batch configuration
        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'job_id': job_id,
                'scout_account_id': scout_account_id,
                'application_name': application_name,
                'source_hash': source_hash,
                'batches': batches,
                'total_batches': total_batches,
                'total_files': total_files,
                'batch_size': BATCH_SIZE
            }
        }

    except Exception as e:
        print(f"Error preparing refactor batches: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch preparation failed: {str(e)}")


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
