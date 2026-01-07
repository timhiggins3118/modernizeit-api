#!/usr/bin/env python3
"""
Code Refactor V2 - Merge Refactor Batches V2
Combines all AI refactor batch pattern results into single ai_patterns.json

Uses shared job context helpers for consistent path handling.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add shared module to path for Lambda deployment
handler_dir = Path(__file__).parent
shared_dir = handler_dir.parent.parent / 'shared'
if shared_dir.exists():
    sys.path.insert(0, str(shared_dir))

try:
    from refactor_v2_common import get_refactor_job_context, error_response
    from ai_config import get_ai_config
except ImportError:
    # Fallback for local testing
    from shared.refactor_v2_common import get_refactor_job_context, error_response
    from shared.ai_config import get_ai_config

s3_client = boto3.client('s3')


def lambda_handler(event, context):
    """
    Merge all AI refactor batch results into single ai_patterns.json
    Reads from ai_patterns/batch_*.json files
    """

    try:
        print(f"MergeRefactorBatchesV2 starting: {json.dumps(event)}")

        # Get job context using shared helper
        job_ctx = get_refactor_job_context(event)
        bucket = job_ctx.bucket_name

        # Get batch counts from event
        total_batches = event.get('total_batches', 0)
        total_files = event.get('total_files', 0)

        print(f"Job context: job_id={job_ctx.job_id}, job_root={job_ctx.job_root}")
        print(f"Merging {total_batches} refactor batch results for job: {job_ctx.job_id}")

        # Get AI config for logging
        ai_cfg = get_ai_config()

        # Collect all batch results
        all_files = []
        batches_found = 0
        files_analyzed = 0
        files_failed = 0

        for batch_id in range(total_batches):
            batch_key = job_ctx.get_batch_key('ai_patterns', batch_id)

            try:
                # Read batch result
                batch_response = s3_client.get_object(Bucket=bucket, Key=batch_key)
                batch_data = json.loads(batch_response['Body'].read().decode('utf-8'))

                # Add files from this batch
                batch_files = batch_data.get('files', [])
                all_files.extend(batch_files)

                # Track statistics
                batches_found += 1
                files_analyzed += batch_data.get('files_processed', 0)
                files_failed += batch_data.get('files_failed', 0)

                print(f"Batch {batch_id}: {len(batch_files)} files")

            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    print(f"Warning: Batch {batch_id} result not found")
                    # Continue merging other batches
                else:
                    raise

        print(f"Found {batches_found}/{total_batches} batches, {files_analyzed} files analyzed")

        # Create merged output
        merged_output = {
            'job_id': job_ctx.job_id,
            'source_hash': job_ctx.source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'ai_config': {
                'provider': ai_cfg.provider,
                'region': ai_cfg.region,
                'model_id': ai_cfg.model_id
            },
            'batch_mode': True,
            'total_batches': total_batches,
            'batches_processed': batches_found,
            'files_expected': total_files,
            'files_analyzed': files_analyzed,
            'files_failed': files_failed,
            'files': all_files
        }

        # Write merged result to S3 using job context helper
        output_key = job_ctx.get_artifact_key('ai_patterns.json')
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=json.dumps(merged_output, indent=2),
            ContentType='application/json'
        )

        print(f"Merge complete. Output written to: {output_key}")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'job_id': job_ctx.job_id,
                'batches_processed': batches_found,
                'files_analyzed': files_analyzed,
                'files_failed': files_failed,
                'output_path': f"s3://{bucket}/{output_key}"
            }
        }

    except ValueError as e:
        # Missing required fields
        print(f"Validation error: {str(e)}")
        return error_response(400, str(e))

    except Exception as e:
        print(f"Error merging refactor batches: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch merge failed: {str(e)}")
