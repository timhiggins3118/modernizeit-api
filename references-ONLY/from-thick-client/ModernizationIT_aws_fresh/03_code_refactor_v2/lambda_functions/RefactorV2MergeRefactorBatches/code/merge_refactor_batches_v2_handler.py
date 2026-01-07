#!/usr/bin/env python3
"""
Code Refactor V2 - Merge Refactor Batches V2
Combines all AI refactor batch pattern results into single ai_patterns.json
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Merge all AI refactor batch results into single ai_patterns.json
    Reads from ai_patterns/batch_*.json files
    """

    try:
        print(f"MergeRefactorBatchesV2 starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')
        total_batches = event.get('total_batches', 0)
        total_files = event.get('total_files', 0)

        if not all([job_id, scout_account_id, application_name]):
            return error_response(400, 'Missing required fields')

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_refactor_v2/jobs/{job_id}"
        batch_prefix = f"{job_path}/artifacts/ai_patterns/batch_"

        print(f"Merging {total_batches} refactor batch results for job: {job_id}")

        # Collect all batch results
        all_files = []
        batches_found = 0
        files_analyzed = 0
        files_failed = 0

        for batch_id in range(total_batches):
            batch_key = f"{batch_prefix}{batch_id}.json"

            try:
                # Read batch result
                batch_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=batch_key)
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
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'agent_id': 'TBD',  # COBOLRefactorAnalystV2
            'agent_name': 'COBOLRefactorAnalystV2',
            'batch_mode': True,
            'total_batches': total_batches,
            'batches_processed': batches_found,
            'files_expected': total_files,
            'files_analyzed': files_analyzed,
            'files_failed': files_failed,
            'files': all_files
        }

        # Write merged result to S3
        output_key = f"{job_path}/artifacts/ai_patterns.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(merged_output, indent=2),
            ContentType='application/json'
        )

        print(f"Merge complete. Output written to: {output_key}")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'job_id': job_id,
                'batches_processed': batches_found,
                'files_analyzed': files_analyzed,
                'files_failed': files_failed,
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error merging refactor batches: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch merge failed: {str(e)}")


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
