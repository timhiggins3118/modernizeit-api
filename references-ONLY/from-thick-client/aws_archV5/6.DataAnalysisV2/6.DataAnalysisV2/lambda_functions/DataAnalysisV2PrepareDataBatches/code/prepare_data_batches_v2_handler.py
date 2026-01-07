#!/usr/bin/env python3
"""
Data Analyzer V2 - Prepare Data Batches Handler
Splits COBOL files into batches for parallel AI data analysis
"""

import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'
BATCH_SIZE = 5  # Files per batch for AI analysis

def lambda_handler(event, context):
    """
    Prepare batches of COBOL files for AI data analysis
    Input: job_id, scout_account_id, application_name, source_hash
    Output: List of batches with file paths
    """

    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Preparing data analysis batches for job: {job_id}")

        # Read classified catalog to get COBOL files
        base_path = f"{scout_account_id}/{application_name}"
        catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"

        catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        # Get COBOL files
        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            print("No COBOL files found in catalog")
            return {
                'statusCode': 200,
                'body': {
                    'batches': [],
                    'total_batches': 0,
                    'total_files': 0,
                    'message': 'No COBOL files to analyze'
                }
            }

        total_files = len(cobol_files)
        print(f"Found {total_files} COBOL files")

        # Create batches
        batches = []
        for i in range(0, total_files, BATCH_SIZE):
            batch = {
                'batch_id': i // BATCH_SIZE,
                'files': cobol_files[i:i + BATCH_SIZE]
            }
            batches.append(batch)

        total_batches = len(batches)
        print(f"Created {total_batches} batches ({BATCH_SIZE} files per batch)")

        return {
            'statusCode': 200,
            'body': {
                'batches': batches,
                'total_batches': total_batches,
                'total_files': total_files,
                'batch_size': BATCH_SIZE
            }
        }

    except Exception as e:
        print(f"Error preparing data batches: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {
                'error': str(e)
            }
        }
