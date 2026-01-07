#!/usr/bin/env python3
"""
Code Refactor V2 - Prepare Refactor Batches V2
Splits COBOL files into processable batches for parallel AI pattern analysis

Uses shared job context helpers for consistent path handling.
Uses SAME catalog reading logic as RegexPatternDetector and ASTPatternDetector.
"""

import json
import sys
import os
import logging
from math import ceil
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add shared module to path for Lambda deployment
handler_dir = Path(__file__).parent
shared_dir = handler_dir.parent.parent / 'shared'
if shared_dir.exists():
    sys.path.insert(0, str(shared_dir))

try:
    from refactor_v2_common import get_refactor_job_context, error_response
except ImportError:
    # Fallback for local testing
    from shared.refactor_v2_common import get_refactor_job_context, error_response

s3_client = boto3.client('s3')

# Configuration
BATCH_SIZE = 5  # Files per batch


def lambda_handler(event, context):
    """
    Prepare batches of COBOL files for parallel AI pattern analysis
    Reads classified catalog and splits files into batches

    Uses SAME catalog reading logic as RegexPatternDetector and ASTPatternDetector.
    """

    try:
        print(f"PrepareRefactorBatchesV2 starting: {json.dumps(event)}")

        # Get job context using shared helper
        job_ctx = get_refactor_job_context(event)
        bucket = job_ctx.bucket_name

        print(f"Job context: job_id={job_ctx.job_id}, job_root={job_ctx.job_root}")
        print(f"Catalog prefix: {job_ctx.catalog_prefix}")

        # Read classified catalog to get COBOL files
        # SAME logic as RegexPatternDetector and ASTPatternDetector
        catalog_key = job_ctx.get_catalog_key()
        print(f"Reading catalog from: s3://{bucket}/{catalog_key}")

        try:
            catalog_response = s3_client.get_object(Bucket=bucket, Key=catalog_key)
            classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            print(f"ERROR: Failed to read catalog - {error_code}: {str(e)}")
            print(f"Catalog key attempted: {catalog_key}")
            return error_response(404, f"Catalog not found: {catalog_key}")

        # Log catalog structure for debugging
        print(f"Catalog keys: {list(classified_catalog.keys())}")
        if 'classifications' in classified_catalog:
            classifications = classified_catalog['classifications']
            print(f"Classifications keys: {list(classifications.keys())}")
            for key, value in classifications.items():
                if isinstance(value, list):
                    print(f"  {key}: {len(value)} items")
                else:
                    print(f"  {key}: {type(value)}")

        # Get COBOL files - SAME logic as RegexPatternDetector/ASTPatternDetector
        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            print("WARNING: No COBOL files found in catalog['classifications']['cobol']")
            print(f"Full catalog structure: {json.dumps(classified_catalog, indent=2)[:1000]}")
            logger.warning(
                "PrepareRefactorBatches: no COBOL files found in catalog",
                extra={"catalog_key": catalog_key}
            )
            return {
                'statusCode': 200,
                'body': {
                    'status': 'completed',
                    'job_id': job_ctx.job_id,
                    'scout_account_id': job_ctx.scout_account_id,
                    'application_name': job_ctx.application_name,
                    'source_hash': job_ctx.source_hash,
                    'batches': [],
                    'total_batches': 0,
                    'total_files': 0,
                    'message': 'No COBOL files found in classified_catalog.json'
                }
            }

        print(f"Found {len(cobol_files)} COBOL files to batch for AI pattern analysis")

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

        print(f"Created {len(batches)} batches for AI pattern analysis of {total_files} files")

        # Return batch configuration
        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'job_id': job_ctx.job_id,
                'scout_account_id': job_ctx.scout_account_id,
                'application_name': job_ctx.application_name,
                'source_hash': job_ctx.source_hash,
                'batches': batches,
                'total_batches': total_batches,
                'total_files': total_files,
                'batch_size': BATCH_SIZE
            }
        }

    except ValueError as e:
        # Missing required fields
        print(f"Validation error: {str(e)}")
        return error_response(400, str(e))

    except Exception as e:
        print(f"Error preparing refactor batches: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch preparation failed: {str(e)}")
