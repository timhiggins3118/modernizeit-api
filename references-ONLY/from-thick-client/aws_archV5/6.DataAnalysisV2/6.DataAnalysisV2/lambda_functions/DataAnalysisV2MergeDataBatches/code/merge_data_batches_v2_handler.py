#!/usr/bin/env python3
"""
Data Analyzer V2 - Merge Data Batches Handler
Merges all AI data analysis batch results into single file
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Merge all AI data analysis batch results
    Input: job_id, scout_account_id, application_name, source_hash, total_batches
    Output: Merged ai_data_analysis.json
    """

    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']
        total_batches = event['total_batches']

        print(f"Merging {total_batches} AI data analysis batches for job: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        batch_prefix = f"{base_path}/data_analysis_v2/jobs/{job_id}/artifacts/ai_data_analysis/"

        all_results = []
        total_files = 0

        # Read all batch results
        for batch_id in range(total_batches):
            batch_key = f"{batch_prefix}batch_{batch_id}.json"

            try:
                batch_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=batch_key)
                batch_data = json.loads(batch_response['Body'].read().decode('utf-8'))

                all_results.extend(batch_data.get('results', []))
                total_files += batch_data.get('files_analyzed', 0)

            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    print(f"Warning: Batch {batch_id} not found, skipping")
                else:
                    raise

        # Create merged output
        merged_output = {
            'job_id': job_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_batches': total_batches,
                'total_files_analyzed': total_files
            },
            'file_analyses': all_results
        }

        # Save merged results
        output_key = f"{base_path}/data_analysis_v2/jobs/{job_id}/artifacts/ai_data_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(merged_output, indent=2),
            ContentType='application/json'
        )

        print(f"Merge complete: {total_files} files from {total_batches} batches")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'total_files': total_files,
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error merging data batches: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
